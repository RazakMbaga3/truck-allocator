"""
app/config.py — Application configuration via pydantic-settings.
"""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Odoo 15 Connection ────────────────────────────────────────
    odoo_url: str = "http://odoo.lakecement.co.tz:8069"
    odoo_db: str = "lakecement_prod"
    odoo_username: str = "truck_allocator_svc"
    odoo_password: str = ""

    odoo_picking_type_outgoing_id: int = 2
    odoo_location_stock_id: int = 8
    odoo_location_customer_id: int = 5

    # ── Anthropic AI ─────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── Application ──────────────────────────────────────────────
    app_port: int = 8001
    app_secret_key: str = "dev-secret-change-me"
    app_api_key: str = "dev-api-key-change-me"

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./return_trucks.db"

    # ── Scoring weights (must sum to 1.0) ────────────────────────
    score_weight_capacity: float = 0.35
    score_weight_route: float = 0.40
    score_weight_urgency: float = 0.25

    # ── Algorithm thresholds ─────────────────────────────────────
    default_max_detour_km: float = 80.0
    near_ready_score_penalty: float = 0.70
    avg_truck_capacity_tonnes: float = 30.0

    # ── Scheduler ────────────────────────────────────────────────
    odoo_sync_interval_minutes: int = 15
    rematch_before_eta_hours: int = 24

    # ── Computed: Odoo RM item codes ─────────────────────────────
    @computed_field
    @property
    def rm_item_codes(self) -> dict[str, str]:
        return {
            "COAL":     "RM000001",
            "GYPSUM":   "RM000003",
            "IRON_ORE": "RM000004",
            "CLINKER":  "RM000014",
        }

    # ── Computed: per-corridor maximum detour ────────────────────
    @computed_field
    @property
    def corridor_max_detour_km(self) -> dict[str, float]:
        return {
            "CENTRAL":           self.default_max_detour_km,
            "NORTHERN":          self.default_max_detour_km,
            "SOUTHERN_HIGHLAND": self.default_max_detour_km * 1.5,
            "LAKE":              self.default_max_detour_km * 2.0,
            "COASTAL":           self.default_max_detour_km * 0.75,
            "SOUTHERN":          self.default_max_detour_km,
        }

    # ── Computed: daily truck arrival rates ──────────────────────
    @computed_field
    @property
    def daily_truck_rates(self) -> dict[str, float]:
        return {
            "CLINKER":  20.0,
            "COAL":     11.0,
            "GYPSUM":    4.0,
            "IRON_ORE":  1.0,
        }

    # ── Computed: Odoo reference prefixes ────────────────────────
    @computed_field
    @property
    def odoo_ref_prefixes(self) -> dict[str, str]:
        return {
            "purchase_order": "LPORD",
            "grn":            "CM/GRN",
            "sale_order":     "SO",
            "delivery_order": "DO",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
