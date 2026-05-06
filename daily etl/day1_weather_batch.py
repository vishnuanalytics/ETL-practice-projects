import os
import psycopg2
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ++++++++++++++++++++ Configs ++++++++++++++++++++++++
API_KEY = os.getenv('OPENWEATHER_API_KEY')
DB_URL = os.getenv('NEON_DATABASE_URL')

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
CITIES = [
    "Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Kochi"
]

# ++++++++++++++++++++++++ Extract +++++++++++++++++++++++++++

def fetch_weather(city:str)->dict|None:
    try:
        response = requests.get(
            BASE_URL,
            params={"q":f"{city}", "appid":API_KEY, "units":"metrics"}
            )
        response.raise_for_status()
        data = response.json()
        return {
            "city": data.get("name", {}),
            "country": data['sys']['country'],
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
            "wind_speed":  data["wind"]["speed"]
        }
        
    except requests.HTTPError as e:
        print(f"  [HTTP error] {city}: {e}")
    except KeyError as e:
        print(f"[parse error] {city}: {e}")
    except requests.RequestException as e:
        print(f"  [Network error] {city}: {e}")

    return None

# +++++++++++++++++++++++++ Transform +++++++++++++++++++++++++++++++++++++++++++++

def transform(raw:dict) ->dict:

    return {
        **raw,
        "description": raw["description"].title(),
        "wind_speed": round(raw["wind_speed"],2)

    }

# ++++++++++++++++++++++++++ Load ++++++++++++++++++++++++++++++++++++++++++++

def load_batch(records: list[dict])->int:

    sql = """
        INSERT INTO weather_snapshots
            (city, country, temp_celsius, feels_like, humidity, description, wind_speed)
        VALUES
            (%(city)s, %(country)s, %(temp)s, %(feels_like)s,
                %(humidity)s, %(description)s, %(wind_speed)s)
    """

    inserted = 0
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as curr:
            for record in records:
                curr.execute(sql, record)
                inserted += 1
        conn.commit()

    return inserted


# ++++++++++++++++++++++++++ Pipeline ++++++++++++++++++++++++++++++

def run():
    print(f"  Weather Batch ETL — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Extraction of city wise weather data
    print(f"\n[Extract] Fetching {len(CITIES)} cities...")
    raw_records = []
    for city in CITIES:
        result = fetch_weather(city)
        if result:
            raw_records.append(result)
            print(f"{city:15} {result['temp']}°C  {result['description']}")
        else:
            print(f"{city:15} skipped")

    print(f"\n  Fetched: {len(raw_records)}/{len(CITIES)}")

    # Transforming the desctiption & wind speed

    cleaned_records = [transform(r) for r in raw_records]
    print(f"Transformation is done")

    # Writing to the db
    print(f"Initiated to the database")
    count = load_batch(cleaned_records)

    print(f"Inserted {count} rows")

if __name__ == "__main__":
    run()
