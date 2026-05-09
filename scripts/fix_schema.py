"""Add missing columns to existing SQLite DB and verify savings_ledger table."""
import sqlite3

conn = sqlite3.connect('return_trucks.db')
cur = conn.cursor()

# Check existing columns
existing = {row[1] for row in cur.execute("PRAGMA table_info(truck_schedules)").fetchall()}
print("Existing truck_schedules columns:", sorted(existing))

missing = []
if 'transporter_name' not in existing:
    missing.append("ALTER TABLE truck_schedules ADD COLUMN transporter_name VARCHAR(200)")
if 'driver_license_no' not in existing:
    missing.append("ALTER TABLE truck_schedules ADD COLUMN driver_license_no VARCHAR(50)")
if 'dealer_number' not in existing:
    missing.append("ALTER TABLE truck_schedules ADD COLUMN dealer_number VARCHAR(50)")

for sql in missing:
    print("Running:", sql)
    cur.execute(sql)

# Check savings_ledger
tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
print("Tables:", sorted(tables))

if 'savings_ledger' not in tables:
    print("Creating savings_ledger table...")
    cur.execute("""
        CREATE TABLE savings_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL UNIQUE REFERENCES allocation_proposals(id),
            schedule_id INTEGER NOT NULL REFERENCES truck_schedules(id),
            proposal_ref VARCHAR(30) NOT NULL,
            schedule_ref VARCHAR(30) NOT NULL,
            truck_plate VARCHAR(20),
            transporter_name VARCHAR(200),
            corridor_name VARCHAR(50),
            origin_region VARCHAR(50),
            fresh_freight_avoided_tzs FLOAT NOT NULL DEFAULT 0.0,
            return_freight_paid_tzs FLOAT NOT NULL DEFAULT 0.0,
            holding_cost_saved_tzs FLOAT NOT NULL DEFAULT 0.0,
            net_savings_tzs FLOAT NOT NULL DEFAULT 0.0,
            allocated_tonnes FLOAT NOT NULL DEFAULT 0.0,
            capacity_utilization_pct FLOAT NOT NULL DEFAULT 0.0,
            number_of_orders INTEGER NOT NULL DEFAULT 0,
            dispatch_date DATETIME,
            month_key VARCHAR(7),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("savings_ledger created.")
else:
    count = cur.execute("SELECT COUNT(*) FROM savings_ledger").fetchone()[0]
    print(f"savings_ledger already exists with {count} rows.")

conn.commit()
conn.close()
print("Done.")
