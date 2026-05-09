import sqlite3
conn = sqlite3.connect('return_trucks.db')
cur = conn.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('TABLES:', [t[0] for t in tables])
try:
    rows = cur.execute('SELECT COUNT(*) FROM savings_ledger').fetchone()
    print('savings_ledger rows:', rows[0])
    sample = cur.execute('SELECT * FROM savings_ledger LIMIT 1').fetchone()
    cols = [d[0] for d in cur.description]
    print('savings_ledger columns:', cols)
    if sample:
        print('sample row (net_savings):', sample[cols.index('net_savings_tzs')])
        print('sample row (month_key):', sample[cols.index('month_key')])
except Exception as e:
    print('savings_ledger ERROR:', e)
conn.close()
