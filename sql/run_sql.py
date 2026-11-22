"""Run the SQL files in order with DuckDB and print every result.
Usage (from the repo root):  python sql/run_sql.py
"""
from pathlib import Path
import duckdb

con = duckdb.connect()
for f in sorted(Path('sql').glob('0*.sql')):
    print(f'\n######## {f.name} ########')
    for stmt in [s.strip() for s in f.read_text(encoding='utf-8').split(';')]:
        body = '\n'.join(l for l in stmt.splitlines() if not l.strip().startswith('--')).strip()
        if not body:
            continue
        res = con.sql(body)
        if res is not None:
            print(res.df().to_string(index=False), '\n')
