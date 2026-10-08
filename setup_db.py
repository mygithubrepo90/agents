import sqlite3

conn = sqlite3.connect("retail.db")       # creates the file if it doesn't exist
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS sales")  # start fresh every time you run this
cur.execute("""
    CREATE TABLE sales (
        sale_date TEXT,
        store     TEXT,
        product   TEXT,
        units     INTEGER,
        price     REAL
    )
""")

rows = [
    ("2026-09-28", "12", "Amul butter", 40, 52.5),
    ("2026-09-29", "12", "Amul butter", 45, 52.5),
    ("2026-09-30", "12", "Amul butter", 35, 52.5),
    ("2026-10-05", "12", "Amul butter", 30, 55.0),
    ("2026-10-06", "12", "Amul butter", 42, 55.0),
    ("2026-09-29", "7",  "Amul butter", 60, 52.5),
    ("2026-10-05", "7",  "Amul butter", 65, 52.5),
    ("2026-09-30", "12", "Britannia bread", 80, 40.0),
    ("2026-10-06", "12", "Britannia bread", 75, 40.0),
    ("2026-10-05", "7",  "Britannia bread", 50, 40.0),
]
cur.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?)", rows)

conn.commit()
print("Rows in sales:", cur.execute("SELECT COUNT(*) FROM sales").fetchone()[0])
conn.close()