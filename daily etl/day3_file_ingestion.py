import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path
import csv

load_dotenv()
DB_URL = os.getenv("NEON_DATABASE_URL")
DATA_DIR = Path(__file__).parent.parent/"data"



# ============ World Population CSV (clean, straightforward) ===========================

def run_population(path:Path):
    df = pd.read_csv(path)
    print(f"Extracted: {len(df)} rows")

    # Transform the column names
    df = df.rename(columns={
        "Rank": "rank", "CCA3": "cca3", 
        "Country/Territory": "country", "Capital": "capital",
        "Continent": "continent","2022 Population": "pop_2022",
        "2020 Population": "pop_2020", "2015 Population": "pop_2015",
        "2010 Population":"pop_2010","2000 Population": "pop_2000",
        "1990 Population": "pop_1990","1980 Population": "pop_1980",
        "1970 Population": "pop_1970","Area (km²)": "area_km2",
        "Density (per km²)": "density_per_km2",
        "Growth Rate": "growth_rate", "World Population Percentage": "world_pct"
    })

    print(f"renamed the columns: {df.columns}")

    for col in ["rank", "pop_2022", "pop_2020", "pop_2015", "pop_2010",
                "pop_2000", "pop_1990", "pop_1980", "pop_1970", "area_km2"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in ["density_per_km2", "growth_rate", "world_pct"]:
        df[col] = pd.to_numeric(df[col],errors="coerce")

    df = df.dropna(subset=["cca3","country"])
    records = df.where(pd.notna(df), None).to_dict(orient='records')
    print(f"  Transformed: {len(records)} clean rows")

    sql = """
        INSERT INTO world_population(
            rank, cca3, country, capital, continent,
            pop_2022, pop_2020, pop_2015, pop_2010, pop_2000,
            pop_1990, pop_1980, pop_1970,
            area_km2, density_per_km2, growth_rate, world_pct
        ) values %s
        on conflict (cca3) do update set
            rank = excluded.rank, pop_2022 = excluded.pop_2022,
            fetched_at = now()
    """

    rows = [(
        r["rank"], r["cca3"], r["country"], r["capital"], r["continent"],
        r["pop_2022"], r["pop_2020"], r["pop_2015"], r["pop_2010"], r["pop_2000"],
        r["pop_1990"], r["pop_1980"], r["pop_1970"],
        r["area_km2"], r["density_per_km2"], r["growth_rate"], r["world_pct"]
    ) for r in records]

    _bulk_upsert(sql,rows)
    print(f"  Loaded: {len(rows)} rows → world_population")


# +++++++++++++++++ db caller +++++++++++++++++++++++++++++++++++++
def _bulk_upsert(sql:str, rows:list):
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=100)
        conn.commit()


# ================= pipeline ===============================

SOURCES = [
    (DATA_DIR/"world_population.csv",  run_population),
]

def run():

    print(f"  File Ingestion ETL — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Sources: {len(SOURCES)} files")

    for filename, handler in SOURCES:
        path = Path(filename)

        if not path.exists():
            print(f"\nSkipping {filename} — file not found")
            continue
        try:
            handler(path)
        except Exception as e:
             print(f"\n {filename} failed: {e}")
    print(f"Done.")

if __name__ == "__main__":
    run()
