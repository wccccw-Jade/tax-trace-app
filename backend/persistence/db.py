from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.config import settings

@lru_cache
def engine():
    return create_engine(settings.database_url, pool_pre_ping=True, connect_args={'connect_timeout': 3})

def session():
    with Session(engine()) as db:
        yield db
