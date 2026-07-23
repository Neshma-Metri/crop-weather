import os, sqlalchemy
from dotenv import load_dotenv

load_dotenv()
engine = sqlalchemy.create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    print(conn.execute(sqlalchemy.text("select 1")).scalar())