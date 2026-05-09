"""
tests/test_odoo_sync.py — Odoo sync service tests with mocked XML-RPC.

These tests mock the xmlrpc.client.ServerProxy so no real Odoo connection is needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOdooClient:
    """Test the OdooClient XML-RPC wrapper."""

    def setup_method(self):
        from app.services.odoo_sync import OdooClient
        self.client = OdooClient()

    @patch("xmlrpc.client.ServerProxy")
    def test_authenticate_returns_uid(self, mock_proxy):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 42
        mock_proxy.return_value = mock_common

        self.client._uid = None
        uid = self.client.authenticate()
        assert uid == 42

    @patch("xmlrpc.client.ServerProxy")
    def test_authenticate_failure_raises(self, mock_proxy):
        mock_common = MagicMock()
        mock_common.authenticate.return_value = False
        mock_proxy.return_value = mock_common

        self.client._uid = None
        with pytest.raises(ConnectionError):
            self.client.authenticate()

    def test_fetch_rm_purchase_orders_filters_eligible(self):
        """Only POs flagged as x_return_load_eligible should be returned."""
        from app.services.odoo_sync import OdooClient

        client = OdooClient()
        client._uid = 1

        mock_pos = [
            {"id": 1, "name": "LPORD/2026/00001", "state": "purchase",
             "partner_id": [10, "Test Transporter"], "scheduled_date": "2026-04-30",
             "date_order": "2026-04-27", "order_line": [], "picking_ids": []},
        ]

        with patch.object(client, "_execute") as mock_exec:
            # First call: PO list; second call: x_return_load_eligible filter
            mock_exec.side_effect = [
                mock_pos,            # fetch all confirmed POs
                [{"id": 1}],         # eligible IDs
                [],                  # PO lines (empty)
            ]
            result = client.fetch_rm_purchase_orders()
            assert len(result) == 1
            assert result[0]["name"] == "LPORD/2026/00001"

    def test_ping_returns_connected_true(self):
        from app.services.odoo_sync import OdooClient
        client = OdooClient()

        with patch.object(client, "_common") as mock_common_fn:
            mock_common_instance = MagicMock()
            mock_common_instance.version.return_value = {"server_version": "15.0"}
            mock_common_instance.authenticate.return_value = 5
            mock_common_fn.return_value = mock_common_instance

            result = client.ping()
            assert result["connected"] is True
            assert result["uid"] == 5


class TestOdooSyncService:
    """Test OdooSyncService with mocked OdooClient."""

    @pytest.mark.asyncio
    async def test_sync_sale_orders_upserts(self, db):
        from app.services.odoo_sync import OdooSyncService

        svc = OdooSyncService(db)

        mock_sos = [{
            "id": 99001,
            "name": "SO/2026/99001",
            "state": "sale",
            "partner_id": [1001, "Test Customer"],
            "commitment_date": "2026-05-10",
            "amount_total": 5_000_000,
            "order_line": [],
            "picking_ids": [],
            "_dispatch_ready": True,
            "_credit_cleared": True,
            "_loading_priority": 2,
            "_lines": [],
        }]

        with patch.object(svc.client, "fetch_sale_orders", return_value=mock_sos):
            stats = await svc.sync_sale_orders()

        assert stats["upserted"] == 1

        # Verify it's in DB
        from app.models import CementOrder
        from sqlalchemy import select
        result = await db.execute(
            select(CementOrder).where(CementOrder.odoo_order_id == 99001)
        )
        order = result.scalar_one_or_none()
        assert order is not None
        assert order.dispatch_ready is True
        assert order.odoo_order_name == "SO/2026/99001"

    @pytest.mark.asyncio
    async def test_sync_sale_orders_second_call_updates(self, db):
        """Calling sync twice should not duplicate records."""
        from app.services.odoo_sync import OdooSyncService
        from app.models import CementOrder
        from sqlalchemy import select, func

        svc = OdooSyncService(db)
        mock_sos = [{
            "id": 99002,
            "name": "SO/2026/99002",
            "state": "sale",
            "partner_id": [1002, "Another Customer"],
            "commitment_date": None,
            "amount_total": 2_000_000,
            "order_line": [],
            "picking_ids": [],
            "_dispatch_ready": False,
            "_credit_cleared": False,
            "_loading_priority": 3,
            "_lines": [],
        }]

        with patch.object(svc.client, "fetch_sale_orders", return_value=mock_sos):
            await svc.sync_sale_orders()
            await svc.sync_sale_orders()  # Second call

        result = await db.execute(
            select(func.count(CementOrder.id)).where(CementOrder.odoo_order_id == 99002)
        )
        count = result.scalar()
        assert count == 1  # No duplicate
