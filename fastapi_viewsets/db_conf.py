import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

from fastapi_viewsets import BASE_DIR

load_dotenv(f"{BASE_DIR}.env")

SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL') or f"sqlite:///{BASE_DIR}base.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
Base.query = db_session.query_property()

def get_session():
    return SessionLocal()
