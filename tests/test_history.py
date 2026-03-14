"""
test_history.py — tests for time-windowed reading endpoints.

Covers:
- /readings/history?hours=N edge cases
- /readings/hour-ago approximate lookup
"""

import pytest
from datetime import datetime, timedelta, timezone
from conftest import RAMP_DATA


# ===========================================================================
# /readings/history
# ===========================================================================

class TestHistory:
    def test_returns_all_ramp_rows_within_last_hour(self, seeded_client):
        """All ramp points sit within the last 50 min so all should appear."""
        c, ids = seeded_client
        r = c.get("/readings/history?hours=1")
        assert r.status_code == 200
        assert len(r.json()) == len(RAMP_DATA)

    def test_excludes_readings_outside_window(self, seeded_client):
        """Every returned reading must have a timestamp within the requested window."""
        c, ids = seeded_client
        r = c.get("/readings/history?hours=1")
        data = r.json()
        cutoff = datetime.now() - timedelta(hours=1)
        for row in data:
            raw = row["timestamp"].replace("Z", "").replace("+00:00", "")
            ts = datetime.fromisoformat(raw)
            assert ts >= cutoff, f"Reading {row['id']} is outside the 1-hour window"

    def test_hours_defaults_to_one(self, seeded_client):
        """Calling /readings/history with no param defaults to 1 hour."""
        c, ids = seeded_client
        r = c.get("/readings/history")
        assert r.status_code == 200
        assert len(r.json()) == len(RAMP_DATA)

    def test_hours_zero_returns_empty(self, client):
        """hours=0 is a zero-width window — nothing qualifies."""
        r = client.get("/readings/history?hours=0")
        assert r.status_code == 200
        assert r.json() == []

    def test_hours_negative_returns_empty(self, client):
        """Negative hours sets the cutoff in the future — nothing qualifies."""
        r = client.get("/readings/history?hours=-1")
        assert r.status_code == 200
        assert r.json() == []

    def test_hours_very_large_returns_all(self, seeded_client):
        """A very large window should encompass everything in the DB."""
        c, ids = seeded_client
        r = c.get("/readings/history?hours=9999")
        assert r.status_code == 200
        assert len(r.json()) == len(RAMP_DATA)


# ===========================================================================
# /readings/hour-ago
# ===========================================================================

class TestHourAgo:
    def test_returns_404_when_no_data(self, client):
        """Empty DB — no reading near 1 hour ago."""
        r = client.get("/readings/at-offset")
        assert r.status_code == 404

    def test_returns_404_when_no_reading_in_window(self, client, auth_headers):
        """Readings exist but none fall within ±5 min of 1 hour ago."""
        # All ramp data is within the last 50 min, nothing near 60 min ago
        r = client.get("/readings/at-offset")
        assert r.status_code == 404

    def test_returns_reading_within_five_minute_window(self, client, auth_headers):
        """A reading seeded at exactly 60 min ago should be returned."""
        from models import SensorReading
        from db import get_db

        db_gen = client.app.dependency_overrides[get_db]()
        db = next(db_gen)

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        db.add(SensorReading(
            timestamp=one_hour_ago,
            temperature=19.5,
            humidity=52.0,
            pressure=101000,
        ))
        db.commit()

        r = client.get("/readings/at-offset")
        assert r.status_code == 200
        assert r.json()["temperature"] == 19.5

    def test_returns_closest_reading_when_multiple_in_window(self, client, auth_headers):
        """When two readings fall within ±5 min, return the closer one."""
        from models import SensorReading
        from db import get_db

        db_gen = client.app.dependency_overrides[get_db]()
        db = next(db_gen)

        now = datetime.now(timezone.utc)
        # 58 min ago — 2 min from target, should win
        closer = SensorReading(
            timestamp=now - timedelta(minutes=58),
            temperature=18.0, humidity=50.0, pressure=101000,
        )
        # 64 min ago — 4 min from target
        further = SensorReading(
            timestamp=now - timedelta(minutes=64),
            temperature=17.0, humidity=50.0, pressure=101000,
        )
        db.add_all([closer, further])
        db.commit()

        r = client.get("/readings/at-offset")
        assert r.status_code == 200
        assert r.json()["temperature"] == 18.0
