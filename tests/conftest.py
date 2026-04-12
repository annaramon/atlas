import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.models.base import Base


@pytest.fixture()
def db_session():
    """In-memory SQLite session with all tables created. Dropped after each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def patched_db(db_session):
    """Patches app.agent.tools.SessionLocal so tools use the test SQLite session."""
    from unittest.mock import patch

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=db_session)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.agent.tools.SessionLocal", return_value=cm):
        yield db_session
