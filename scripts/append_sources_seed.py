import csv
from urllib.parse import urlparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "store" / "sources_seed.csv"
SQL_PATH = ROOT / "scripts" / "postgres-init.sql"

def main():
    if not CSV_PATH.exists():
        print(f"Error: {CSV_PATH} not found.")
        return

    # Read the existing SQL content
    sql_content = SQL_PATH.read_text(encoding="utf-8")

    # If the file already contains -- Seed sources, truncate it there
    seed_marker = "-- Seed sources"
    if seed_marker in sql_content:
        sql_content = sql_content.split(seed_marker)[0].strip() + "\n"

    # Read sources from CSV
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source_id = row["source_id"].strip()
            name = row["name"].strip()
            url = row["url"].strip()
            type_val = row["type"].strip()
            category = row["category"].strip()
            note = row["note"].strip()

            parsed = urlparse(url)
            domain = parsed.netloc

            # Format fields for SQL (escape single quotes)
            def escape(s):
                return s.replace("'", "''")

            rows.append(
                f"('{escape(source_id)}', '{escape(name)}', '{escape(url)}', '{escape(url)}', '{escape(domain)}', '{escape(type_val)}', '{escape(category)}', '{escape(note)}')"
            )

    if not rows:
        print("No sources to seed.")
        return

    # Build seed SQL
    seed_sql = f"\n{seed_marker}\n"
    seed_sql += "INSERT INTO sources (source_id, name, url, base_url, domain, type, category, note) VALUES\n"
    seed_sql += ",\n".join(rows)
    seed_sql += "\nON CONFLICT (source_id) DO NOTHING;\n"

    # Write back to init script
    SQL_PATH.write_text(sql_content + seed_sql, encoding="utf-8")
    print(f"Successfully appended {len(rows)} sources to {SQL_PATH}")

if __name__ == "__main__":
    main()
