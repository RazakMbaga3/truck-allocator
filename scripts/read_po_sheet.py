"""Find actual data rows in the RM Purchase Order sheets."""
import openpyxl
from pathlib import Path

BASE = Path(__file__).parent.parent
path = BASE / "Raw Material -Transporter Mater, Supplier Master & RM Purchase-25.04.xlsx"

wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)

for sheet_name in ["RM Purchase Order-Coal", "RM Purchase Order-Clinker", "RM Purchase Order-Gypsum", "RM Purchase Order-Iron ore "]:
    ws = wb[sheet_name]
    print(f"\n{'='*60}")
    print(f"Sheet: {sheet_name}")
    print(f"{'='*60}")
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=12, values_only=True)):
        if any(v is not None for v in row):
            # Show first 10 non-None values
            vals = [(j, v) for j, v in enumerate(row) if v is not None][:10]
            print(f"  Row {i+1}: {vals}")

wb.close()
