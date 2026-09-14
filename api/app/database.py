import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "aiops_sentinel")
PG_ADMIN_USER = os.getenv("PG_ADMIN_USER", "aiops")
PG_ADMIN_PASSWORD = os.getenv("PG_ADMIN_PASSWORD", "")

DATABASE_URL = (
    f"postgresql://{PG_ADMIN_USER}:{PG_ADMIN_PASSWORD}"
    f"@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
