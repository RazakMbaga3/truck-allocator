"""
app/services/matching_engine.py — The core matching algorithm.

For each TruckSchedule, finds the best set of CementOrders to load on
the truck's return journey, generates up to 3 allocation proposal variants,
and triggers Claude AI advisory.

Flow:
  1. Load all UNALLOCATED + NEAR_READY orders
  2. Filter by corridor membership (detour <= max_detour_km)
  3. Filter by capacity and dispatch readiness
  4. Score all candidates
  5. Generate 3 variants: BEST_MATCH / MAX_LOAD / URGENT_FIRST
  6. Sequence stops within each variant
  7. Compute totals and utilization
  8. Log MatchingEvent
  9. Save AllocationProposals
 10. Trigger AI advisor (async, non-blocking)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AllocationProposal,
    AllocationStatus,
    CementOrder,
    MatchingEvent,
    MatchTrigger,
    OrderAllocationStatus,
    ProposalItem,
    ProposalStatus,
    ProposalVariant,
    TruckSchedule,
    TruckScheduleStatus,
)
from app.services.route_calculator import (
    detour_km,
    is_on_corridor,
    sort_stops_by_route_order,
)
from app.services.scoring import CandidateScore, score_candidate
from app.services.freight_savings import compute_savings

logger = logging.getLogger(__name__)
settings = get_settings()


class MatchingEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def match(
        self,
        schedule: TruckSchedule,
        trigger: str = MatchTrigger.PO_SYNC,
    ) -> list[AllocationProposal]:
        start_ms = int(time.monotonic() * 1000)
        logger.info("Matching schedule %s (origin=%s)", schedule.schedule_ref, schedule.origin_region)

        all_orders = await self._load_candidates(schedule)
        orders_evaluated = len(all_orders)

        qualified = self._filter_candidates(all_orders, schedule)
        orders_qualified = len(qualified)

        if not qualified:
            logger.info(
                "No qualified candidates for %s (evaluated=%d)",
                schedule.schedule_ref, orders_evaluated,
            )
            event = MatchingEvent(
                schedule_id=schedule.id,
                triggered_by=trigger,
                orders_evaluated=orders_evaluated,
                orders_qualified=0,
                proposals_generated=0,
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            )
            self.session.add(event)
            return []

        scored = self._score_all(qualified, schedule)
        proposals = self._generate_variants(scored, schedule)

        for proposal in proposals:
            self._sequence_stops(proposal, schedule)
            self._compute_totals(proposal, schedule)

        top_util = max((p.capacity_utilization_pct for p in proposals), default=0.0)

        event = MatchingEvent(
            schedule_id=schedule.id,
            triggered_by=trigger,
            orders_evaluated=orders_evaluated,
            orders_qualified=orders_qualified,
            proposals_generated=len(proposals),
            top_utilization_pct=top_util,
            ai_called=True,
            duration_ms=int(time.monotonic() * 1000) - start_ms,
        )
        self.session.add(event)

        for proposal in proposals:
            self.session.add(proposal)

        if proposals:
            schedule.allocation_status = AllocationStatus.PROPOSED

        await self.session.flush()

        proposal_ids = [p.id for p in proposals]
        asyncio.create_task(self._trigger_ai(schedule.id, proposal_ids))

        logger.info(
            "Match complete: %s → %d proposals, top util %.0f%%",
            schedule.schedule_ref, len(proposals), top_util,
        )
        return proposals

    async def rematch(
        self,
        schedule: TruckSchedule,
        trigger: str = MatchTrigger.REMATCH,
    ) -> list[AllocationProposal]:
        result = await self.session.execute(
            select(AllocationProposal).where(
                AllocationProposal.schedule_id == schedule.id,
                AllocationProposal.status == ProposalStatus.PROPOSED,
            )
        )
        old_proposals = result.scalars().all()
        for p in old_proposals:
            p.status = ProposalStatus.REJECTED

        return await self.match(schedule, trigger=trigger)

    # ── Private: Load ─────────────────────────────────────────────

    async def _load_candidates(self, schedule: TruckSchedule) -> list[CementOrder]:
        result = await self.session.execute(
            select(CementOrder).where(
                CementOrder.allocation_status.in_([
                    OrderAllocationStatus.UNALLOCATED,
                    OrderAllocationStatus.CANDIDATE,
                ]),
                CementOrder.return_load_eligible == True,
            )
        )
        return result.scalars().all()

    # ── Private: Filter ───────────────────────────────────────────

    def _filter_candidates(
        self,
        orders: list[CementOrder],
        schedule: TruckSchedule,
    ) -> list[CementOrder]:
        max_detour = schedule.max_detour_km
        truck_eta = schedule.expected_arrival_dt

        qualified = []
        for order in orders:
            region = order.delivery_region
            if not region:
                continue

            dev = detour_km(region.upper(), schedule.origin_region.upper())
            if dev > max_detour:
                continue

            if order.quantity_tonnes <= 0:
                continue

            is_firm = order.dispatch_ready and order.credit_cleared
            is_near = (
                order.near_ready
                and (
                    truck_eta is None
                    or order.near_ready_eta is None
                    or order.near_ready_eta <= truck_eta
                )
            )

            if not is_firm and not is_near:
                continue

            qualified.append(order)

        return qualified

    # ── Private: Score ────────────────────────────────────────────

    def _score_all(
        self,
        orders: list[CementOrder],
        schedule: TruckSchedule,
    ) -> list[tuple[CementOrder, CandidateScore]]:
        results = []
        for order in orders:
            region = order.delivery_region or "DODOMA"
            dev = detour_km(region.upper(), schedule.origin_region.upper())
            is_near = not (order.dispatch_ready and order.credit_cleared)

            sc = score_candidate(
                order_id=order.id,
                order_name=order.odoo_order_name,
                delivery_region=order.delivery_region,
                quantity_tonnes=order.quantity_tonnes,
                deadline_dt=order.deadline_dt,
                dispatch_ready=order.dispatch_ready,
                detour_km=dev,
                truck_capacity_tonnes=schedule.effective_capacity_tonnes,
                is_near_ready=is_near,
            )
            results.append((order, sc))

        return results

    # ── Private: Generate variants ────────────────────────────────

    def _generate_variants(
        self,
        scored: list[tuple[CementOrder, CandidateScore]],
        schedule: TruckSchedule,
    ) -> list[AllocationProposal]:
        proposals = []
        capacity = schedule.effective_capacity_tonnes

        # A: BEST_MATCH — sort by composite score DESC
        sorted_a = sorted(scored, key=lambda x: x[1].composite_score, reverse=True)
        prop_a = self._greedy_pack(sorted_a, capacity, ProposalVariant.BEST_MATCH, schedule)
        if prop_a:
            proposals.append(prop_a)

        # B: MAX_LOAD — sort by quantity_tonnes DESC
        sorted_b = sorted(scored, key=lambda x: x[0].quantity_tonnes, reverse=True)
        prop_b = self._greedy_pack(sorted_b, capacity, ProposalVariant.MAX_LOAD, schedule)
        if prop_b and not _same_orders(prop_b, prop_a):
            proposals.append(prop_b)

        # C: URGENT_FIRST — sort by urgency_score DESC then deadline ASC
        sorted_c = sorted(
            scored,
            key=lambda x: (
                -x[1].urgency_score,
                x[0].deadline_dt or datetime.max.replace(tzinfo=timezone.utc),
            ),
        )
        prop_c = self._greedy_pack(sorted_c, capacity, ProposalVariant.URGENT_FIRST, schedule)
        if prop_c and not _same_orders(prop_c, prop_a) and not _same_orders(prop_c, prop_b):
            proposals.append(prop_c)

        return proposals

    def _greedy_pack(
        self,
        sorted_candidates: list[tuple[CementOrder, CandidateScore]],
        capacity_tonnes: float,
        variant: str,
        schedule: TruckSchedule,
    ) -> AllocationProposal | None:
        if not sorted_candidates:
            return None

        items: list[tuple[CementOrder, CandidateScore, float]] = []
        remaining = capacity_tonnes
        has_near_ready = False
        near_ready_notes: list[str] = []

        for order, sc in sorted_candidates:
            if remaining <= 0:
                break

            allocate_tonnes = order.quantity_tonnes
            if allocate_tonnes > remaining:
                if order.partial_load_allowed:
                    allocate_tonnes = remaining
                else:
                    continue

            items.append((order, sc, allocate_tonnes))
            remaining -= allocate_tonnes

            if sc.is_near_ready:
                has_near_ready = True
                eta_str = (
                    order.near_ready_eta.strftime("%a %d %b %H:%M")
                    if order.near_ready_eta else "ETA unknown"
                )
                near_ready_notes.append(
                    f"{order.odoo_order_name} ({order.delivery_region}, {allocate_tonnes}T) "
                    f"— dispatch_ready ETA {eta_str}"
                )

        if not items:
            return None

        variant_letter = {"BEST_MATCH": "A", "MAX_LOAD": "B", "URGENT_FIRST": "C"}.get(variant, "X")
        ref = f"{schedule.schedule_ref.replace('SCHED', 'PROP')}-{variant_letter}"

        proposal = AllocationProposal(
            proposal_ref=ref,
            schedule_id=schedule.id,
            variant_type=variant,
            has_pending_readiness_orders=has_near_ready,
            pending_readiness_note="\n".join(near_ready_notes) if near_ready_notes else None,
            status=ProposalStatus.PROPOSED,
        )
        self.session.add(proposal)

        for seq, (order, sc, allocated_tonnes) in enumerate(items, start=1):
            item = ProposalItem(
                proposal=proposal,
                cement_order=order,
                cement_order_id=order.id,
                allocated_tonnes=allocated_tonnes,
                allocated_bags=int(allocated_tonnes * 20),
                sequence=seq,
                delivery_deviation_km=sc.detour_km,
                is_near_ready=sc.is_near_ready,
            )
            self.session.add(item)

        return proposal

    # ── Private: Sequence + Totals ────────────────────────────────

    def _sequence_stops(self, proposal: AllocationProposal, schedule: TruckSchedule) -> None:
        if not proposal.items:
            return
        corridor = schedule.corridor_name or "CENTRAL"
        regions = [item.cement_order.delivery_region or "" for item in proposal.items]
        sorted_regions = sort_stops_by_route_order(regions, corridor, reverse=True)
        region_to_seq = {r: i + 1 for i, r in enumerate(sorted_regions)}
        for item in proposal.items:
            region = item.cement_order.delivery_region or ""
            item.sequence = region_to_seq.get(region, item.sequence)

    def _compute_totals(
        self, proposal: AllocationProposal, schedule: TruckSchedule
    ) -> None:
        if not proposal.items:
            return

        total_tonnes = sum(i.allocated_tonnes for i in proposal.items)
        total_dev = sum(i.delivery_deviation_km for i in proposal.items)
        capacity = schedule.effective_capacity_tonnes
        util_pct = (total_tonnes / capacity * 100) if capacity > 0 else 0.0
        total_fresh = 0.0
        total_return = 0.0
        total_holding = 0.0
        total_savings = 0.0

        for item in proposal.items:
            order = item.cement_order
            if not order:
                continue

            allocated_ratio = (
                item.allocated_tonnes / order.quantity_tonnes
                if order.quantity_tonnes > 0 else 1.0
            )
            fresh_freight = (
                order.fresh_outbound_freight_tzs * allocated_ratio
                if order.fresh_outbound_freight_tzs
                else None
            )
            savings = compute_savings(
                order_id=order.id,
                order_ref=order.odoo_order_name,
                distance_km=order.distance_from_plant_km or 0.0,
                tonnes=item.allocated_tonnes,
                corridor=order.delivery_corridor or schedule.corridor_name,
                deadline_dt=order.deadline_dt,
            )

            if fresh_freight is not None:
                return_freight = fresh_freight * 0.60
                gross = fresh_freight - return_freight
                net = gross + savings.holding_cost_saved_tzs
                total_fresh += fresh_freight
                total_return += return_freight
                total_holding += savings.holding_cost_saved_tzs
                total_savings += net
                item.item_savings_tzs = round(net, 0)
            else:
                total_fresh += savings.fresh_freight_tzs
                total_return += savings.return_freight_tzs
                total_holding += savings.holding_cost_saved_tzs
                total_savings += savings.net_saving_tzs
                item.item_savings_tzs = round(savings.net_saving_tzs, 0)

        if total_tonnes > 0:
            composite = sum(
                i.allocated_tonnes / total_tonnes * i.delivery_deviation_km
                for i in proposal.items
            )
            composite = max(0.0, min(1.0, 1.0 - composite / (capacity * 100)))
        else:
            composite = 0.0

        proposal.total_allocated_tonnes = total_tonnes
        proposal.capacity_utilization_pct = round(util_pct, 1)
        proposal.total_route_deviation_km = round(total_dev, 1)
        proposal.number_of_stops = len({i.cement_order.delivery_region for i in proposal.items})
        proposal.total_fresh_freight_tzs = round(total_fresh, 0)
        proposal.total_return_freight_tzs = round(total_return, 0)
        proposal.holding_cost_tzs = round(total_holding, 0)
        proposal.estimated_savings_tzs = round(total_savings, 0)
        proposal.composite_score = round(composite, 4)

    # ── Private: AI trigger ───────────────────────────────────────

    async def _trigger_ai(self, schedule_id: int, proposal_ids: list[int]) -> None:
        try:
            from app.services.ai_advisor import TruckAllocationAdvisor
            from app.database import AsyncSessionLocal

            async with AsyncSessionLocal() as ai_session:
                result = await ai_session.execute(
                    select(TruckSchedule).where(TruckSchedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()
                if not schedule:
                    return

                result2 = await ai_session.execute(
                    select(AllocationProposal).where(AllocationProposal.id.in_(proposal_ids))
                )
                proposals = result2.scalars().all()

                if schedule and proposals:
                    advisor = TruckAllocationAdvisor()
                    await advisor.advise(schedule, proposals, ai_session)
                    await ai_session.commit()
        except Exception as e:
            logger.error("AI advisor error for schedule %d: %s", schedule_id, e)


def _same_orders(a: AllocationProposal | None, b: AllocationProposal | None) -> bool:
    if a is None or b is None:
        return False
    ids_a = {item.cement_order_id for item in a.items}
    ids_b = {item.cement_order_id for item in b.items}
    return ids_a == ids_b
