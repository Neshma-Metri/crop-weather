"""
Day 1 Streamlit app: monsoon rainfall explorer for Chhatrapati Sambhajinagar.

Deliberately minimal. The goal is a working deployed URL, not a finished product.
"""

import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Monsoon Explorer", layout="wide")


def get_db_url() -> str:
    """Prefer Streamlit secrets (cloud); fall back to .env (local)."""
    from dotenv import load_dotenv
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        st.error("DATABASE_URL not set. Add it to .env locally, or to Secrets on Streamlit Cloud.")
        st.stop()
    return url


@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    engine = create_engine(get_db_url())
    df = pd.read_sql("SELECT * FROM daily_weather ORDER BY date;", engine)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    return df


st.title("Monsoon Rainfall Explorer")
st.caption("Chhatrapati Sambhajinagar, Maharashtra — daily records since 1960")

df = load_data()

# --- Annual rainfall totals ---
st.subheader("Total rainfall by year (mm)")
annual = df.groupby("year")["precipitation_sum"].sum()
annual = annual.drop(index=annual.index.max())  # drop incomplete current year
st.bar_chart(annual)

# --- Single-year detail ---
st.subheader("Daily rainfall within a single year")
year = st.slider(
    "Year", int(df["year"].min()), int(annual.index.max()), int(annual.index.max())
)
one_year = df[df["year"] == year].set_index("date")
st.line_chart(one_year["precipitation_sum"])

# --- Sanity check ---
with st.expander("Raw data"):
    st.dataframe(df.tail(200), use_container_width=True)

st.info(
    "Descriptive tool showing historical patterns only. Not a forecast, "
    "and not agronomic advice."
)
