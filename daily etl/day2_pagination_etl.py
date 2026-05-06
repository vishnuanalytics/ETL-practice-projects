import os
import time
import psycopg2
import requests
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# +++++++++++++++++++++++++ Configs ++++++++++++++++++++++++++++++++++++++++++
DB_URL = os.getenv("NEON_DATABASE_URL")
BASE_URL = "http://universities.hipolabs.com/search"

# +++++++++++++++++++++++++++Extract ++++++++++++++++++++++++++++++++

def fetch_page(country:str, offset:int, limit:int) ->list[dict]:
    try:
        response = requests.get(
            BASE_URL,
            params = {"country":country,"offset":offset, "limit":limit}
        )
        response.raise_for_status()
        return response.json()

    except requests.HTTPError as e:
        print(e)
    except requests.RequestException as e:
        print(e)
    return []
        
def fetch_all_universities(country:str, page_size:int=20)->list[dict]:
    all_records = []
    offset = 0
    page_num=1

    while True:
        page = fetch_page(country, offset, page_size)

        if not page:
            break
        all_records.extend(page)

        if len(page) < page_size:
            break

        offset += page_size
        page_num +=1
        time.sleep(0.3)

    return all_records


def transform(raw:dict)->dict:
    name = (raw.get("name") or "").strip()
    if not name:
        return None
    
    websites = raw.get('web_pages') or []
    website = websites[0].strip() if websites else None

    return {
        "name": name,
        "country": (raw.get("country") or "").strip(),
        "alpha_two_code": (raw.get("alpha_two_code") or "").strip().upper(),
        "state_province": (raw.get("state-province") or "").strip() or None,
        "website": website
    }

def transform_all(raw_records:list[dict])->list[dict]:
    cleaned = [transform(r) for r in raw_records]
    valid = [r for r in cleaned if r is not None]
    discarded = len(raw_records) - len(valid)

    if discarded:
        print(f"  ⚠ Discarded {discarded} invalid records")
    return valid

def load_batch(records: list[dict])->tuple[int,int]:

    if not records:
        return 0,0
    
    sql = """
        INSERT INTO universities (name, country, alpha_two_code, state_province, website)
        VALUES %s
        ON CONFLICT (name, country) DO NOTHING
    """

    rows = [
        (r["name"], r["country"], r["alpha_two_code"], r["state_province"], r["website"])
        for r in records
    ]

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=100)
            inserted = cur.rowcount

    skipped = len(records) - inserted
    return inserted, skipped

COUNTRIES = ["India", "United States", "United Kingdom"]

def run():
    print(f"\n{'='*55}")
    print(f"  University Pagination ETL — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}")

    total_inserted = 0
    total_skipped  = 0

    for country in COUNTRIES:
        # 1. Extract — pagination loop
        raw = fetch_all_universities(country, page_size=20)
        print(f"  Total fetched: {len(raw)}")

        # 2. Transform
        print(f"\n[Transform] Cleaning records...")
        clean = transform_all(raw)
        print(f" {len(clean)} valid records")

        # 3. Load
        print(f"\n[Load] Upserting to Neon...")
        inserted, skipped = load_batch(clean)
        print(f"Inserted: {inserted}  |  Skipped (dupes): {skipped}")

        total_inserted += inserted
        total_skipped  += skipped

    print(f"\n{'='*55}")
    print(f"  Done.  Inserted: {total_inserted}  |  Skipped: {total_skipped}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    run()
