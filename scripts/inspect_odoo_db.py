"""Inspect what products and partners exist in local Odoo DB."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import xmlrpc.client

URL = "http://localhost:8069"
DB  = "Razak"
USER = "digital@lakecement.co.tz"
PWD  = "Mbagarazack617@"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USER, PWD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def ex(model, method, domain, kw=None):
    return models.execute_kw(DB, uid, PWD, model, method, [domain], kw or {})

print("=" * 60)
print("PRODUCTS")
print("=" * 60)
products = ex("product.template", "search_read", [["active", "=", True]],
              {"fields": ["id", "name", "type", "default_code"], "limit": 30})
for p in products:
    print(f"  [{p['id']}] {p['name']}  code={p['default_code']}  type={p['type']}")

print()
print("=" * 60)
print("CUSTOMERS (first 15)")
print("=" * 60)
customers = ex("res.partner", "search_read", [["customer_rank", ">", 0]],
               {"fields": ["id", "name", "ref", "city"], "limit": 15})
for p in customers:
    print(f"  [{p['id']}] {p['name']}  ref={p['ref']}  city={p['city']}")

print()
print("=" * 60)
print("VENDORS / SUPPLIERS (first 15)")
print("=" * 60)
vendors = ex("res.partner", "search_read", [["supplier_rank", ">", 0]],
             {"fields": ["id", "name", "ref", "city"], "limit": 15})
for v in vendors:
    print(f"  [{v['id']}] {v['name']}  ref={v['ref']}  city={v['city']}")

print()
print("=" * 60)
print("PURCHASE ORDERS (existing)")
print("=" * 60)
pos = ex("purchase.order", "search_read", [],
         {"fields": ["id", "name", "state", "partner_id", "date_order"], "limit": 10})
for po in pos:
    print(f"  {po['name']}  state={po['state']}  partner={po['partner_id']}  date={po['date_order']}")

print()
print("=" * 60)
print("SALE ORDERS (existing)")
print("=" * 60)
sos = ex("sale.order", "search_read", [],
         {"fields": ["id", "name", "state", "partner_id", "date_order"], "limit": 10})
for so in sos:
    print(f"  {so['name']}  state={so['state']}  partner={so['partner_id']}  date={so['date_order']}")
