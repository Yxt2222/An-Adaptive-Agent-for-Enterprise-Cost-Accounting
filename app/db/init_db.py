from app.db.session import get_engine
from app.db.base import Base

def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
