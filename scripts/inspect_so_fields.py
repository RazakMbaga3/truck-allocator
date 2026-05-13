"""
scripts/inspect_so_fields.py

Connects to Odoo via XML-RPC and prints all custom fields on sale.order
so you can confirm the exact technical names for truck/driver/trip details.

Run:
    python scripts/inspect_so_fields.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_settings
from app.services.odoo_sync import OdooClient

settings = get_settings()
client = OdooClient()

print(f"\nConnecting to {settings.odoo_url} ...")
ping = client.ping()
if not ping["connected"]:
    print(f"ERROR: {ping.get('error')}")
    sys.exit(1)
print(f"Connected as UID {ping['uid']} (Odoo {ping['odoo_version']})\n")

# Get all fields on sale.order
uid = client._uid_or_auth()
all_fields = client._models().execute_kw(
    settings.odoo_db, uid, settings.odoo_password,
    "sale.order", "fields_get",
    [],
    {"attributes": ["string", "type", "store"]},
)

# Filter: custom (x_) fields + known trip-related field names
keywords = ["truck", "trailer", "driver", "license", "trip", "vehicle",
            "schedule", "corridor", "plate", "mobile", "phone", "transporter"]

print("=" * 70)
print("CUSTOM FIELDS (x_*) on sale.order:")
print("=" * 70)
custom = {k: v for k, v in all_fields.items() if k.startswith("x_")}
if custom:
    for fname, finfo in sorted(custom.items()):
        print(f"  {fname:<40} {finfo['type']:<12} '{finfo['string']}'")
else:
    print("  (none found — x_schedule_ref and trip fields may not exist yet)")

print()
print("=" * 70)
print("TRIP/TRUCK-RELATED FIELDS (all fields matching keywords):")
print("=" * 70)
matched = {
    k: v for k, v in all_fields.items()
    if any(kw in k.lower() or kw in v["string"].lower() for kw in keywords)
}
if matched:
    for fname, finfo in sorted(matched.items()):
        print(f"  {fname:<40} {finfo['type']:<12} '{finfo['string']}'")
else:
    print("  (no matching fields found)")

print()
print("=" * 70)
print("HOW TO USE THESE RESULTS:")
print("=" * 70)
print("Copy the exact field names above into your .env file:")
print()
print("  ODOO_SO_FIELD_TRUCK_NO=<field name for Truck No>")
print("  ODOO_SO_FIELD_TRAILER_NO=<field name for Trailer No>")
print("  ODOO_SO_FIELD_DRIVER_NAME=<field name for Driver Name>")
print("  ODOO_SO_FIELD_DRIVER_PHONE=<field name for Driver Mobile>")
print("  ODOO_SO_FIELD_DRIVER_LICENSE=<field name for Driver License>")
print("  ODOO_SO_FIELD_SCHEDULE_REF=<x_schedule_ref — create if missing>")
print()
