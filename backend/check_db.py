import sqlite3

con = sqlite3.connect('../data/aegis.db')
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in ["threats", "incidents", "evidence"]:
    if t in tables:
        print(f"\nSample from {t}:")
        cols = [d[0] for d in cur.execute(f"SELECT * FROM {t} LIMIT 1").description]
        print("Cols:", cols)
        for row in cur.execute(f"SELECT * FROM {t} LIMIT 5").fetchall():
            print(row[:4])
