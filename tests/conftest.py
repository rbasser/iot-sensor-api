"""
conftest.py — shared fixtures for the sensor API test suite.

Design decisions:
- One in-memory SQLite DB per test function (scope="function") — complete isolation,
  no state bleeds between tests.
- `seeded_client` builds a known ramp dataset directly via the ORM (bypasses the API
  and its validation layer), so tests that need pre-existing data start from a
  predictable baseline without depending on POST working correctly first.
- `client` gives a clean empty DB for tests that want to start from zero.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from db import Base, get_db
from main import app, API_KEY_SECRET
from models import SensorReading

# ---------------------------------------------------------------------------
# Ramp dataset — 10 readings, 5 minutes apart, all within valid bounds.
# Temperature ramps 20.0 → 20.9, humidity ramps 55.0 → 55.9, pressure fixed.
# Timestamps start 50 minutes ago so the full set falls within the last hour.
# ---------------------------------------------------------------------------
BASE_TIME = datetime.now(timezone.utc) - timedelta(minutes=50)

RAMP_DATA = [
    {
        "temperature": round(20.0 + i * 0.1, 1),
        "humidity":    round(55.0 + i * 0.1, 1),
        "pressure":    101000,
        "timestamp":   BASE_TIME + timedelta(minutes=i * 5),
        "reboot_flag": True if i == 0 else None,
    }
    for i in range(10)
]

# Expected values derived from RAMP_DATA — use these in assertions so the
# tests are self-documenting and stay in sync if RAMP_DATA ever changes.
RAMP_LATEST_TEMP = RAMP_DATA[-1]["temperature"]   # 20.9
RAMP_LATEST_HUM  = RAMP_DATA[-1]["humidity"]       # 55.9
RAMP_FIRST_ID_OFFSET = 0                           # relative index into seeded IDs


def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _make_client(engine):
    """Wire a TestClient to the given engine via dependency override."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture()
def client():
    """Empty database — use for tests that build their own state via the API."""
    engine = _make_engine()
    c = _make_client(engine)
    yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_client():
    """
    Pre-populated database containing RAMP_DATA inserted directly via ORM.
    Also exposes the list of inserted IDs so tests can reference them precisely.
    Returns (client, ids) where ids[0] is the oldest reading, ids[-1] the newest.
    """
    engine = _make_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed via ORM — bypasses API validation intentionally, gives us known IDs.
    db = SessionLocal()
    instances = [SensorReading(**row) for row in RAMP_DATA]
    db.add_all(instances)
    db.commit()
    for inst in instances:
        db.refresh(inst)
    ids = [inst.id for inst in instances]
    db.close()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)

    yield c, ids

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": API_KEY_SECRET}
