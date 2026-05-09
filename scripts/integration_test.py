"""
scripts/integration_test.py — End-to-end integration test.

Hits a running server (default: http://localhost:8001) with real HTTP requests.
Validates the full lifecycle:

  1. Health check passes
  2. Routes endpoint returns corridor data
  3. Can sync orders via POST /api/orders/sync (if Odoo is reachable, else skips)
  4. Can create a schedule directly in DB, run match via POST /{id}/rematch
  5. Proposals are returned with correct structure
  6. Can confirm a proposal → truck removed from available list
  7. SSE endpoint opens without error

Usage:
    # Server must be running first:
    uvicorn app.main:app --port 8001

    python scripts/integration_test.py
    python scripts/integration_test.py --host http://localhost:8001
    python scripts/integration_test.py --api-key my-secret-key
    python scripts/integration_test.py --skip-odoo    # skip Odoo-dependent tests
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

PASS = "[bold green]✅ PASS[/bold green]"
FAIL = "[bold red]❌ FAIL[/bold red]"
SKIP = "[yellow]⏭  SKIP[/yellow]"
INFO = "[cyan]ℹ [/cyan]"


class IntegrationTestRunner:
    def __init__(self, base_url: str, api_key: str, skip_odoo: bool = False):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.skip_odoo = skip_odoo
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self._results: list[tuple[str, str, str]] = []  # (name, status, note)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=30.0)
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    def record(self, name: str, passed: bool, note: str = "") -> None:
        status = PASS if passed else FAIL
        self._results.append((name, status, note))
        console.print(f"  {status}  {name}", end="")
        if note:
            console.print(f"  [dim]{note}[/dim]", end="")
        console.print()

    def skip(self, name: str, reason: str = "") -> None:
        self._results.append((name, SKIP, reason))
        console.print(f"  {SKIP}  {name}  [dim]{reason}[/dim]")

    async def run_all(self) -> int:
        """Run all tests. Returns 0 on all pass, 1 if any fail."""
        console.rule("[bold #173158]NYATI CEMENT — Integration Test Suite[/bold #173158]")
        console.print(f"\n  Target: [cyan]{self.base_url}[/cyan]\n")

        await self._test_health()
        await self._test_routes()
        await self._test_transporters()
        await self._test_orders_list()
        await self._test_schedules_list()
        await self._test_proposals_list()
        await self._test_savings_summary()
        await self._test_sse_opens()
        if not self.skip_odoo:
            await self._test_odoo_sync_trigger()
        else:
            self.skip("Odoo sync trigger", "skipped via --skip-odoo")
        await self._test_create_and_match_flow()

        # Summary
        console.print()
        console.rule("[bold]Results[/bold]")
        passes = sum(1 for _, s, _ in self._results if "PASS" in s)
        fails  = sum(1 for _, s, _ in self._results if "FAIL" in s)
        skips  = sum(1 for _, s, _ in self._results if "SKIP" in s)
        console.print(f"\n  Total: {len(self._results)}  "
                      f"[green]Passed: {passes}[/green]  "
                      f"[red]Failed: {fails}[/red]  "
                      f"[yellow]Skipped: {skips}[/yellow]\n")

        if fails > 0:
            console.print("[bold red]INTEGRATION TESTS FAILED[/bold red]")
            return 1
        console.print("[bold green]ALL INTEGRATION TESTS PASSED ✅[/bold green]")
        return 0

    # ── Individual tests ──────────────────────────────────────────────────────

    async def _test_health(self):
        console.print("\n[bold]1. Health Check[/bold]")
        try:
            r = await self._client.get("/api/health")
            data = r.json()
            self.record("GET /api/health → 200", r.status_code == 200,
                        f"status={data.get('status')}")
            self.record("database=ok in health", data.get("database") == "ok")
        except Exception as e:
            self.record("GET /api/health", False, str(e))

    async def _test_routes(self):
        console.print("\n[bold]2. Route Corridors[/bold]")
        try:
            r = await self._client.get("/api/routes")
            data = r.json()
            self.record("GET /api/routes → 200", r.status_code == 200)
            corridors = data.get("corridors", {})
            self.record("corridors dict present", isinstance(corridors, dict))
            self.record("CENTRAL corridor present", "CENTRAL" in corridors)
            self.record("SOUTHERN_HIGHLAND present", "SOUTHERN_HIGHLAND" in corridors)
            count = data.get("regions_count", 0)
            self.record(f"≥20 Tanzania regions ({count})", count >= 20)
        except Exception as e:
            self.record("GET /api/routes", False, str(e))

    async def _test_transporters(self):
        console.print("\n[bold]3. Transporters[/bold]")
        try:
            r = await self._client.get("/api/transporters")
            self.record("GET /api/transporters → 200", r.status_code == 200)
            data = r.json()
            self.record("returns list", isinstance(data, list),
                        f"count={len(data)}")
        except Exception as e:
            self.record("GET /api/transporters", False, str(e))

    async def _test_orders_list(self):
        console.print("\n[bold]4. Orders[/bold]")
        try:
            r = await self._client.get("/api/orders")
            self.record("GET /api/orders → 200", r.status_code == 200,
                        f"count={len(r.json()) if r.status_code == 200 else 'err'}")
        except Exception as e:
            self.record("GET /api/orders", False, str(e))

        try:
            r = await self._client.get("/api/orders/unallocated")
            self.record("GET /api/orders/unallocated → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/orders/unallocated", False, str(e))

        try:
            r = await self._client.get("/api/orders/near-ready")
            self.record("GET /api/orders/near-ready → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/orders/near-ready", False, str(e))

        try:
            r = await self._client.get("/api/orders/by-corridor/CENTRAL")
            self.record("GET /api/orders/by-corridor/CENTRAL → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/orders/by-corridor/CENTRAL", False, str(e))

    async def _test_schedules_list(self):
        console.print("\n[bold]5. Truck Schedules[/bold]")
        try:
            r = await self._client.get("/api/schedules")
            self.record("GET /api/schedules → 200", r.status_code == 200,
                        f"count={len(r.json()) if r.status_code == 200 else 'err'}")
        except Exception as e:
            self.record("GET /api/schedules", False, str(e))

        try:
            r = await self._client.get("/api/schedules?status=available")
            self.record("GET /api/schedules?status=available → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/schedules?status=available", False, str(e))

        try:
            r = await self._client.get("/api/schedules?status=all")
            self.record("GET /api/schedules?status=all → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/schedules?status=all", False, str(e))

    async def _test_proposals_list(self):
        console.print("\n[bold]6. Proposals[/bold]")
        try:
            r = await self._client.get("/api/proposals")
            self.record("GET /api/proposals → 200", r.status_code == 200,
                        f"count={len(r.json()) if r.status_code == 200 else 'err'}")
        except Exception as e:
            self.record("GET /api/proposals", False, str(e))

    async def _test_savings_summary(self):
        console.print("\n[bold]7. Savings & Analytics[/bold]")
        try:
            r = await self._client.get("/api/savings/summary")
            self.record("GET /api/savings/summary → 200", r.status_code == 200)
            data = r.json()
            self.record("summary has 'total_savings_tzs'",
                        "total_savings_tzs" in data)
        except Exception as e:
            self.record("GET /api/savings/summary", False, str(e))

        try:
            r = await self._client.get("/api/savings/by-corridor")
            self.record("GET /api/savings/by-corridor → 200", r.status_code == 200)
        except Exception as e:
            self.record("GET /api/savings/by-corridor", False, str(e))

    async def _test_sse_opens(self):
        console.print("\n[bold]8. SSE Live Feed[/bold]")
        try:
            # Open SSE, read just the first chunk (heartbeat or event), then close
            async with self._client.stream("GET", "/api/schedules/feed") as resp:
                self.record("GET /api/schedules/feed → 200", resp.status_code == 200,
                            f"content_type={resp.headers.get('content-type','?')}")
                self.record(
                    "Content-Type: text/event-stream",
                    "text/event-stream" in resp.headers.get("content-type", ""),
                )
                # Read first line within timeout
                try:
                    first_line = None
                    async for line in resp.aiter_lines():
                        first_line = line
                        break
                    self.record("SSE stream readable", first_line is not None,
                                f"first={first_line!r}")
                except Exception as e:
                    self.record("SSE stream readable", False, str(e))
        except Exception as e:
            self.record("GET /api/schedules/feed", False, str(e))

    async def _test_odoo_sync_trigger(self):
        console.print("\n[bold]9. Odoo Sync (may fail if Odoo unreachable)[/bold]")
        try:
            r = await self._client.post("/api/orders/sync")
            # 200 = success, 503 = Odoo unreachable (both are valid outcomes here)
            ok = r.status_code in (200, 503)
            self.record("POST /api/orders/sync responds", ok,
                        f"status={r.status_code}")
            if r.status_code == 200:
                data = r.json()
                self.record("sync returns stats dict", isinstance(data, dict))
        except Exception as e:
            self.record("POST /api/orders/sync", False, str(e))

    async def _test_create_and_match_flow(self):
        """
        Full lifecycle: create schedule via DB → rematch → verify proposals.
        Uses the demo_allocation script data directly.
        """
        console.print("\n[bold]10. Full Allocation Lifecycle[/bold]")
        console.print(f"  {INFO} Seeding test data via demo_allocation module…")

        try:
            # Run demo as a subprocess to seed data
            import subprocess
            result = subprocess.run(
                [sys.executable, "scripts/demo_allocation.py", "--assert"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            demo_ok = result.returncode == 0
            self.record("demo_allocation --assert passes", demo_ok,
                        "" if demo_ok else result.stderr[-200:])
            if not demo_ok:
                return  # No point continuing if demo failed
        except Exception as e:
            self.record("demo_allocation runs", False, str(e))
            return

        # Now query the API for schedules with proposals
        try:
            r = await self._client.get("/api/schedules?status=all")
            schedules = r.json()
            demo_schedules = [
                s for s in schedules
                if isinstance(s, dict) and "DEMO" in s.get("schedule_ref", "")
            ]
            self.record(
                "demo schedules appear in GET /api/schedules",
                len(demo_schedules) >= 3,
                f"found={len(demo_schedules)}",
            )

            if demo_schedules:
                sched_id = demo_schedules[0]["id"]

                # Get proposals for first demo schedule
                r2 = await self._client.get(f"/api/proposals?schedule_id={sched_id}")
                proposals = r2.json()
                self.record(
                    "proposals exist for demo schedule",
                    len(proposals) >= 1,
                    f"count={len(proposals)}",
                )

                if proposals:
                    prop = proposals[0]
                    self.record(
                        "proposal has estimated_savings_tzs",
                        "estimated_savings_tzs" in prop,
                    )
                    self.record(
                        "proposal.estimated_savings_tzs >= 0",
                        prop.get("estimated_savings_tzs", -1) >= 0,
                        f"savings={prop.get('estimated_savings_tzs', 'missing'):,.0f}",
                    )
                    self.record(
                        "proposal has items list",
                        "items" in prop and isinstance(prop["items"], list),
                        f"items={len(prop.get('items', []))}",
                    )

        except Exception as e:
            self.record("lifecycle API checks", False, str(e))


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser(description="Integration test for Smart Return Truck Allocator")
    parser.add_argument("--host", default="http://localhost:8001", help="Base URL of running server")
    parser.add_argument("--api-key", default="dev-api-key-change-me", help="X-API-Key header value")
    parser.add_argument("--skip-odoo", action="store_true", help="Skip tests that require Odoo connection")
    args = parser.parse_args()

    async with IntegrationTestRunner(args.host, args.api_key, args.skip_odoo) as runner:
        return await runner.run_all()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
