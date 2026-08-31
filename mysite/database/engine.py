import os

from sqlalchemy import create_engine, Column, Integer, text
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base, declared_attr

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "2252")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "Warehouse")

bootstrap_engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}", future=True
)
with bootstrap_engine.connect() as conn:
    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}"))
    conn.commit()
bootstrap_engine.dispose()

engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
)

Session = sessionmaker(bind=engine, expire_on_commit=False)

session = scoped_session(Session)


_DeclarativeBase = declarative_base()
