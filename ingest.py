"""
Day 1 ingestion: Open-Meteo historical archive -> Postgres.

Pulls daily weather for Chhatrapati Sambhajinagar (Maharashtra) from 1960 to today.
Idempotent: safe to re-run. Existing dates are updated, not duplicated.
"""

import os
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ["DATABASE_URL"]

LAT, LON = 19.88, 75.34
LOCATION = "chhatrapati_sambhajinagar"
START_DATE = "1960-01-01"

DAILY_VARS = [
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "et0_fao_evapotranspiration",  # reference evapotranspiration = water demand
]


def fetch() -> pd.DataFrame:
    """Fetch the full daily history in one call."""
    end_date = (pd.Timestamp.today() - pd.Timedelta(days=6)).strftime("%Y-%m-%d")

    resp = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": LAT,
            "longitude": LON,
            "start_date": START_DATE,
            "end_date": end_date,
            "daily": ",".join(DAILY_VARS),
            "timezone": "Asia/Kolkata",
        },
        timeout=120,
    )
    resp.raise_for_status()

    df = pd.DataFrame(resp.json()["daily"])
    df = df.rename(columns={"time": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["location"] = LOCATION
    return df


def create_table(engine) -> None:
    """Create the table if it does not exist. Composite PK makes upserts possible."""
    ddl = """
    CREATE TABLE IF NOT EXISTS daily_weather (
        location      TEXT  NOT NULL,
        date          DATE  NOT NULL,
        precipitation_sum          REAL,
        temperature_2m_max         REAL,
        temperature_2m_min         REAL,
        et0_fao_evapotranspiration REAL,
        PRIMARY KEY (location, date)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def upsert(engine, df: pd.DataFrame) -> None:
    """Load via a staging table, then merge. This is what makes re-runs safe."""
    df.to_sql("daily_weather_staging", engine, if_exists="replace", index=False)

    merge_sql = """
    INSERT INTO daily_weather (
        location, date, precipitation_sum, temperature_2m_max,
        temperature_2m_min, et0_fao_evapotranspiration
    )
    SELECT location, date::date, precipitation_sum, temperature_2m_max,
           temperature_2m_min, et0_fao_evapotranspiration
    FROM daily_weather_staging
    ON CONFLICT (location, date) DO UPDATE SET
        precipitation_sum          = EXCLUDED.precipitation_sum,
        temperature_2m_max         = EXCLUDED.temperature_2m_max,
        temperature_2m_min         = EXCLUDED.temperature_2m_min,
        et0_fao_evapotranspiration = EXCLUDED.et0_fao_evapotranspiration;
    """
    with engine.begin() as conn:
        conn.execute(text(merge_sql))
        conn.execute(text("DROP TABLE daily_weather_staging;"))


def main() -> None:
    engine = create_engine(DB_URL)

    print("Fetching...")
    df = fetch()
    print(f"  {len(df):,} rows, {df['date'].min()} to {df['date'].max()}")

    create_table(engine)
    upsert(engine, df)

    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM daily_weather;")).scalar()
    print(f"Done. daily_weather now has {n:,} rows.")


if __name__ == "__main__":
    main()
