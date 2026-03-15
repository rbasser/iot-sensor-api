"""
test_sync.py — daily aggregation and summaries endpoints.

Covers:
- /sync/daily auth, skip conditions, calculation accuracy, idempotency
- /summaries/ ordering and row cap
"""

import pytest
from datetime import datetime, timedelta, timezone
from models import SensorReading, DailySummary
from sqlalchemy.orm import Session


# ===========================================================================
# Helpers
# ===========================================================================

def _get_db(client):
    """Extract the active DB session from the test client's dependency override."""
    from db import get_db
    db_gen = client.app.dependency_overrides[get_db]()
    return next(db_gen)


def _seed_yesterday(db: Session, hours: list[int], temp: float = 22.0,
                    humidity: float = 55.0, reboot_flag: bool = False):
    """
    Seed readings at specific hours of yesterday.
    hours — list of hour values (0–23) to place readings at.
    """
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    instances = [
        SensorReading(
            timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=h)).replace(tzinfo=timezone.utc),
            temperature=temp,
            humidity=humidity,
            pressure=101000,
            reboot_flag=reboot_flag,
        )
        for h in hours
    ]
    db.add_all(instances)
    db.commit()
    return instances


# ===========================================================================
# /sync/daily — auth
# ===========================================================================

class TestDailySyncAuth:
    def test_sync_requires_auth(self, client):
        r = client.post("/sync/daily")
        assert r.status_code == 401

    def test_sync_wrong_key_is_rejected(self, client):
        r = client.post("/sync/daily", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401


# ===========================================================================
# /sync/daily — skip conditions
# ===========================================================================

class TestDailySyncSkip:
    def test_skips_when_no_data_for_yesterday(self, client, auth_headers):
        r = client.post("/sync/daily", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    def test_skips_when_data_span_under_18_hours(self, client, auth_headers):
        """Two readings only 2 hours apart should not produce a summary."""
        db = _get_db(client)
        _seed_yesterday(db, hours=[10, 12])  # only 2h span

        r = client.post("/sync/daily", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

        # No summary should have been written
        assert client.get("/summaries/").json() == []


# ===========================================================================
# /sync/daily — calculation accuracy
# ===========================================================================

class TestDailySyncCalculation:
    def test_calculates_correct_temperature_average(self, client, auth_headers):
        """
        Seed two readings spanning >18h:
          10.0°C at midnight, 20.0°C at 22:00 → avg must be 15.0°C
        """
        db = _get_db(client)
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        db.add_all([
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=0)).replace(tzinfo=timezone.utc),
                temperature=10.0, humidity=50.0, pressure=101000,
            ),
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=22)).replace(tzinfo=timezone.utc),
                temperature=20.0, humidity=60.0, pressure=101000,
            ),
        ])
        db.commit()

        r = client.post("/sync/daily", headers=auth_headers)
        assert r.json()["status"] == "success"

        summary = client.get("/summaries/").json()[0]
        assert summary["avg_temp"]     == 15.0
        assert summary["avg_humidity"] == 55.0

    def test_counts_only_non_null_reboot_flags(self, client, auth_headers):
        """reboot_count should reflect only readings with a non-null reboot_flag."""
        db = _get_db(client)
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        db.add_all([
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=0)).replace(tzinfo=timezone.utc),
                temperature=22.0, humidity=55.0, pressure=101000, reboot_flag=True,
            ),
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=12)).replace(tzinfo=timezone.utc),
                temperature=22.5, humidity=55.5, pressure=101000, reboot_flag=None,
            ),
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=22)).replace(tzinfo=timezone.utc),
                temperature=23.0, humidity=56.0, pressure=101000, reboot_flag=True,
            ),
        ])
        db.commit()

        client.post("/sync/daily", headers=auth_headers)
        assert client.get("/summaries/").json()[0]["reboot_count"] == 2


# ===========================================================================
# /sync/daily — idempotency
# ===========================================================================

class TestDailySyncIdempotency:
    def test_running_twice_does_not_create_duplicate(self, client, auth_headers):
        """Sync is triggered by a cron job — running it twice must be safe."""
        db = _get_db(client)
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        db.add_all([
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=0)).replace(tzinfo=timezone.utc),
                temperature=22.0, humidity=55.0, pressure=101000,
            ),
            SensorReading(
                timestamp=datetime.combine(yesterday, datetime.min.time().replace(hour=22)).replace(tzinfo=timezone.utc),
                temperature=23.0, humidity=56.0, pressure=101000,
            ),
        ])
        db.commit()

        client.post("/sync/daily", headers=auth_headers)
        client.post("/sync/daily", headers=auth_headers)

        assert len(client.get("/summaries/").json()) == 1


# ===========================================================================
# /summaries/
# ===========================================================================

class TestSummaries:

    def _seed_summaries(self, db: Session, n: int):
        today = datetime.now(timezone.utc).date()
        for i in range(n):
            db.add(DailySummary(
                date=today - timedelta(days=i + 1),
                avg_temp=round(20.0 + i * 0.1, 1),
                avg_humidity=55.0,
                avg_pressure=101000,
                reboot_count=0,
            ))
        db.commit()

    def test_empty_returns_empty_list(self, client):
        r = client.get("/summaries/")
        assert r.status_code == 200
        assert r.json() == []

    def test_never_returns_more_than_seven_rows(self, client):
        """Cap at 7 even when 20 rows exist."""
        self._seed_summaries(_get_db(client), 20)
        r = client.get("/summaries/")
        assert r.status_code == 200
        assert len(r.json()) == 7

    def test_returns_newest_first(self, client):
        """Most recent date should be first."""
        self._seed_summaries(_get_db(client), 5)
        dates = [d["date"] for d in client.get("/summaries/").json()]
        assert dates == sorted(dates, reverse=True)
