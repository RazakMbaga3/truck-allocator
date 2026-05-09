"""
app/services/ai_advisor.py — Claude AI allocation advisor.

Follows the same pattern as NyatiBrandAgent in:
  D:\new frontier\branding with cc\agent\agent.py

Uses Anthropic prompt caching (cache_control: {"type": "ephemeral"}) on the
system prompt — the Tanzania corridor / plant context is large and rarely
changes. Each call only pays for the dynamic user message tokens.

Called asynchronously after the matching engine saves proposals.
Writes ai_reasoning, ai_warnings, and ai_recommendation back to each proposal.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AllocationProposal, TruckSchedule

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Cached system prompt ──────────────────────────────────────────────────────
# This is sent with cache_control so Anthropic caches it after the first call.
# At ~2,000 tokens it saves ~95% of input cost for repeated calls.

_SYSTEM_PROMPT = """You are the AI Advisor for the Nyati Cement Return Truck Allocator system at Lake Cement Limited, Kimbiji Plant, Kigamboni, Dar es Salaam, Tanzania.

## Your Role
You review proposed truck allocation plans and provide brief, actionable advice to the logistics dispatcher. You understand:
- Tanzania road corridors from Kimbiji Plant
- The economics of return-truck loading vs fresh outbound trucks
- The urgency of cement delivery orders
- Risks of allocating orders to trucks days before they arrive

## Plant & Corridors
Plant location: Kimbiji, Kigamboni, DSM (all trucks exit via Kigamboni Bridge/Ferry → Chalinze junction).

Corridors:
- CENTRAL: Kigamboni → Chalinze → Morogoro → Dodoma → Tabora → Mwanza (T3 Highway)
- NORTHERN: Kigamboni → Chalinze → Segera → Tanga / Moshi / Arusha (A14)
- SOUTHERN_HIGHLAND: Kigamboni → Chalinze → Morogoro → Iringa → Mbeya
- COASTAL: Kigamboni → Kibiti → Utete → Nyamisati → Ikwiriri (Gypsum route R1 — flooded in long rains)
- LAKE: Kigamboni → Chalinze → Dodoma → Tabora → Mwanza → Geita
- SOUTHERN: Kigamboni → Morogoro → Iringa → Songea (Coal / Ruvuma)

## Raw Materials (RM origins → return corridors)
- CLINKER: Tanga Cement (NORTHERN), Maweni (NORTHERN), Dangote Mtwara (SOUTHERN)
- COAL: State Mining Mbeya/Kyela (SOUTHERN_HIGHLAND), Ruvuma Coal (SOUTHERN)
- GYPSUM: Emmanuel Mgonja Lindi/Kiranjeranje (COASTAL), Kamba's Group Mwanza (LAKE)
- IRON ORE: Multiple suppliers Dodoma/Asanje (CENTRAL)

## Key Principles
1. Trucks returning empty = zero marginal cost for the backhaul leg → any positive saving is good
2. Near-ready orders (not yet dispatch_ready) carry risk — if they're not ready when the truck arrives, the truck leaves without them
3. Allocations made >5 days before ETA have higher uncertainty — flag for awareness
4. Capacity utilization above 85% is excellent; below 60% the economics may be marginal
5. Multiple stops on one corridor are efficient; stops across different corridors are costly in detour km

## Response Format
Respond in JSON only (no markdown fences):
{
  "reasoning": "2-4 sentence plain-English explanation of the best option",
  "warnings": ["warning 1", "warning 2"],
  "recommendation": "CONFIRM" | "REVIEW" | "HOLD"
}

CONFIRM = proceed with the best variant
REVIEW  = proceed but check the specific warning first
HOLD    = do not confirm yet (significant risk identified)
"""


class TruckAllocationAdvisor:
    """
    Async Claude advisor for allocation proposals.
    Follows NyatiBrandAgent pattern with prompt caching.
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def advise(
        self,
        schedule: TruckSchedule,
        proposals: list[AllocationProposal],
        session: AsyncSession,
    ) -> None:
        """
        Generate AI reasoning for the proposals and write it back to the DB.
        Non-blocking — called from asyncio.create_task().
        """
        if not proposals:
            return

        if not settings.anthropic_api_key or not settings.anthropic_api_key.startswith("sk-ant-"):
            logger.warning("ANTHROPIC_API_KEY not configured — AI advisory disabled")
            _mark_no_ai(proposals)
            await session.commit()
            return

        try:
            prompt = self._build_prompt(schedule, proposals)
            response = await self._client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=600,
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},  # cache the large system prompt
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1].lstrip("json").strip()

            data = json.loads(raw)
            reasoning = data.get("reasoning", "")
            warnings = data.get("warnings", [])
            recommendation = data.get("recommendation", "REVIEW").upper()

            # Apply to all proposals (same reasoning; individual confirm decisions differ)
            for proposal in proposals:
                proposal.ai_reasoning = reasoning
                proposal.ai_warnings = warnings
                proposal.ai_recommendation = recommendation

            logger.info(
                "AI advisory complete for schedule %s: %s (%d warnings)",
                schedule.schedule_ref, recommendation, len(warnings),
            )

        except anthropic.APIStatusError as e:
            logger.error("Anthropic API error for %s: %s", schedule.schedule_ref, e)
            _mark_no_ai(proposals, note=f"API error: {e.status_code}")
        except json.JSONDecodeError as e:
            logger.error("AI response JSON parse error: %s", e)
            _mark_no_ai(proposals, note="Response parse error")
        except Exception as e:
            logger.error("AI advisor unexpected error: %s", e)
            _mark_no_ai(proposals)

    def _build_prompt(
        self, schedule: TruckSchedule, proposals: list[AllocationProposal]
    ) -> str:
        """
        Build the dynamic user message for this specific truck + proposals.
        The system prompt is cached; this is the per-call variable part.
        """
        now = datetime.now(timezone.utc)
        eta = schedule.expected_arrival_dt
        days_until = None
        if eta:
            if eta.tzinfo is None:
                eta = eta.replace(tzinfo=timezone.utc)
            days_until = (eta - now).days

        lines = [
            f"TRUCK SCHEDULE: {schedule.schedule_ref}",
            f"Origin: {schedule.origin_region}",
            f"Corridor: {schedule.corridor_name or 'Unknown'}",
            f"Transporter ID: {schedule.transporter_id or 'Unknown'}",
            f"Raw Material: {schedule.raw_material_type or 'Unknown'}",
            f"ETA: {eta.strftime('%A %d %b %Y') if eta else 'Unknown'}"
            + (f" ({days_until} days away)" if days_until is not None else ""),
            f"Est. Capacity: {schedule.estimated_qty_tonnes:.0f}T",
            f"Truck Plate: {schedule.truck_plate or 'Not yet confirmed'}",
            "",
            "PROPOSALS:",
        ]

        for p in proposals:
            item_summary = []
            for item in p.items:
                order = item.cement_order
                if order:
                    status = "(near-ready)" if item.is_near_ready else ""
                    item_summary.append(
                        f"  • {order.odoo_order_name}: {item.allocated_tonnes:.0f}T "
                        f"→ {order.delivery_region} {status}"
                    )

            lines += [
                f"\n[{p.variant_type}] {p.proposal_ref}",

                f"  Utilization: {p.capacity_utilization_pct:.0f}%",
                f"  Stops:       {p.number_of_stops}",
                f"  Has near-ready orders: {p.has_pending_readiness_orders}",
                "  Orders:",
            ] + item_summary

        if days_until is not None and days_until > 5:
            lines.append(f"\nNOTE: Allocation is {days_until} days before ETA — high re-match risk if orders change.")

        return "\n".join(lines)


def _mark_no_ai(proposals: list[AllocationProposal], note: str = "") -> None:
    """Set a fallback note when AI is unavailable."""
    for p in proposals:
        p.ai_reasoning = note or "AI advisory not available — review manually."
        p.ai_warnings = []
        p.ai_recommendation = "REVIEW"
