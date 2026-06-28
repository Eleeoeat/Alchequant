from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.database import get_connection

conn = get_connection(str(ROOT / "data" / "stocks.db"))
df = pd.read_sql_query("""
    SELECT s.code, s.name, COUNT(d.code) as days
    FROM stocks s JOIN daily d ON s.code = d.code
    GROUP BY s.code ORDER BY s.code
""", conn)

out_path = ROOT / "data" / "stock_list.txt"
with open(out_path, "w", encoding="utf-8") as f:
    for _, r in df.iterrows():
        f.write(f"{r['code']} {r['name']} ({r['days']})\n")
print(f"Written {len(df)} stocks to {out_path}")
conn.close()
