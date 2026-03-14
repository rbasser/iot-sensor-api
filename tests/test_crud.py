"""
test_crud.py — CRUD operations for /readings/ endpoints.

Covers:
- Auth enforcement on write endpoints
- Empty DB behaviour
- POST validation and boundary conditions
- GET by ID, latest, all (with skip/limit)
- DELETE lifecycle
- Data integrity across operations
"""

import pytest
from conftest import RAMP_DATA, RAMP_LATEST_TEMP, RAMP_LATEST_HUM


# ===========================================================================
# Auth
# ===========================================================================

class TestAuth:
    def test_post_without_key_is_rejected(self, client):
        payload = {"temperature": 22.0, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload)
        assert r.status_code == 401

    def test_post_with_wrong_key_is_rejected(self, client):
        payload = {"temperature": 22.0, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload, headers={"X-API-Key": "wrong"})
        assert r.status_code == 401
        assert "Invalid or missing API Key" in r.json()["detail"]

    def test_delete_without_key_is_rejected(self, seeded_client):
        c, ids = seeded_client
        r = c.delete(f"/readings/{ids[0]}")
        assert r.status_code == 401

    def test_delete_with_wrong_key_is_rejected(self, seeded_client):
        c, ids = seeded_client
        r = c.delete(f"/readings/{ids[0]}", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401


# ===========================================================================
# Empty database
# ===========================================================================

class TestReadEmpty:
    def test_get_all_returns_empty_list(self, client):
        r = client.get("/readings/")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_latest_returns_404(self, client):
        r = client.get("/readings/latest")
        assert r.status_code == 404
        assert r.json()["detail"] == "No readings found"

    def test_get_by_id_returns_404(self, client):
        r = client.get("/readings/1")
        assert r.status_code == 404
        assert r.json()["detail"] == "Reading Not Found"

    def test_get_history_returns_empty_list(self, client):
        r = client.get("/readings/history?hours=1")
        assert r.status_code == 200
        assert r.json() == []


# ===========================================================================
# POST — create and validate
# ===========================================================================

class TestPost:
    def test_valid_reading_is_saved(self, client, auth_headers):
        payload = RAMP_DATA[0].copy()
        payload.pop("timestamp")
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["temperature"] == payload["temperature"]
        assert data["humidity"]    == payload["humidity"]
        assert data["pressure"]    == payload["pressure"]
        assert "id" in data
        assert "timestamp" in data

    def test_reading_appears_in_get_all_after_post(self, client, auth_headers):
        payload = {"temperature": 21.0, "humidity": 56.0, "pressure": 101000}
        client.post("/readings/", json=payload, headers=auth_headers)
        r = client.get("/readings/")
        assert len(r.json()) == 1

    def test_temperature_at_upper_boundary_is_accepted(self, client, auth_headers):
        payload = {"temperature": 50.0, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["temperature"] == 50.0

    def test_temperature_above_upper_boundary_is_dropped(self, client, auth_headers):
        payload = {"temperature": 50.1, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert "filtered out due to out-of-bounds" in r.json()["detail"]

    def test_temperature_at_lower_boundary_is_accepted(self, client, auth_headers):
        payload = {"temperature": -10.0, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["temperature"] == -10.0

    def test_temperature_below_lower_boundary_is_dropped(self, client, auth_headers):
        payload = {"temperature": -10.1, "humidity": 50.0, "pressure": 101000}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert "filtered out due to out-of-bounds" in r.json()["detail"]

    def test_pressure_at_lower_boundary_is_accepted(self, client, auth_headers):
        payload = {"temperature": 22.0, "humidity": 50.0, "pressure": 80000}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200

    def test_pressure_below_lower_boundary_is_dropped(self, client, auth_headers):
        payload = {"temperature": 22.0, "humidity": 50.0, "pressure": 79999}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.status_code == 200
        assert "filtered out due to out-of-bounds" in r.json()["detail"]

    def test_dropped_reading_is_not_persisted(self, client, auth_headers):
        payload = {"temperature": 99.0, "humidity": 50.0, "pressure": 101000}
        client.post("/readings/", json=payload, headers=auth_headers)
        r = client.get("/readings/")
        assert r.json() == []

    def test_reboot_flag_is_stored(self, client, auth_headers):
        payload = {"temperature": 22.0, "humidity": 50.0, "pressure": 101000, "reboot_flag": "rebooted"}
        r = client.post("/readings/", json=payload, headers=auth_headers)
        assert r.json()["reboot_flag"] == "rebooted"


# ===========================================================================
# GET — seeded ramp dataset
# ===========================================================================

class TestGet:
    def test_get_all_returns_all_ramp_rows(self, seeded_client):
        c, ids = seeded_client
        r = c.get("/readings/")
        assert r.status_code == 200
        assert len(r.json()) == len(RAMP_DATA)

    def test_get_all_is_ordered_newest_first(self, seeded_client):
        c, ids = seeded_client
        data = c.get("/readings/").json()
        assert data[0]["temperature"] == RAMP_LATEST_TEMP

    def test_get_latest_returns_most_recent_ramp_point(self, seeded_client):
        c, ids = seeded_client
        r = c.get("/readings/latest")
        assert r.status_code == 200
        data = r.json()
        assert data["temperature"] == RAMP_LATEST_TEMP
        assert data["humidity"]    == RAMP_LATEST_HUM

    def test_get_by_id_returns_correct_row(self, seeded_client):
        c, ids = seeded_client
        for index, reading_id in [(0, ids[0]), (-1, ids[-1])]:
            r = c.get(f"/readings/{reading_id}")
            assert r.status_code == 200
            assert r.json()["temperature"] == RAMP_DATA[index]["temperature"]

    def test_get_by_nonexistent_id_returns_404(self, seeded_client):
        c, ids = seeded_client
        r = c.get("/readings/999999")
        assert r.status_code == 404

    def test_get_all_limit_param_is_respected(self, seeded_client):
        c, ids = seeded_client
        r = c.get("/readings/?limit=3")
        assert len(r.json()) == 3

    def test_get_all_skip_param_is_respected(self, seeded_client):
        c, ids = seeded_client
        all_data  = c.get("/readings/").json()
        skip_data = c.get("/readings/?skip=2").json()
        assert len(skip_data) == len(RAMP_DATA) - 2
        assert skip_data[0]["id"] == all_data[2]["id"]


# ===========================================================================
# DELETE
# ===========================================================================

class TestDelete:
    def test_delete_returns_deleted_row(self, seeded_client, auth_headers):
        c, ids = seeded_client
        target_id = ids[0]
        r = c.delete(f"/readings/{target_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == target_id

    def test_deleted_row_no_longer_accessible(self, seeded_client, auth_headers):
        c, ids = seeded_client
        target_id = ids[0]
        c.delete(f"/readings/{target_id}", headers=auth_headers)
        r = c.get(f"/readings/{target_id}")
        assert r.status_code == 404

    def test_delete_reduces_total_count(self, seeded_client, auth_headers):
        c, ids = seeded_client
        c.delete(f"/readings/{ids[0]}", headers=auth_headers)
        r = c.get("/readings/")
        assert len(r.json()) == len(RAMP_DATA) - 1

    def test_delete_nonexistent_id_returns_404(self, seeded_client, auth_headers):
        c, _ = seeded_client
        r = c.delete("/readings/999999", headers=auth_headers)
        assert r.status_code == 404

    def test_double_delete_returns_404_on_second_attempt(self, seeded_client, auth_headers):
        c, ids = seeded_client
        target_id = ids[0]
        c.delete(f"/readings/{target_id}", headers=auth_headers)
        r = c.delete(f"/readings/{target_id}", headers=auth_headers)
        assert r.status_code == 404


# ===========================================================================
# Data integrity
# ===========================================================================

class TestDataIntegrity:
    def test_post_then_latest_returns_same_reading(self, client, auth_headers):
        """POST a reading and immediately confirm /readings/latest returns it."""
        payload = {"temperature": 24.7, "humidity": 58.3, "pressure": 101000}
        post_r = client.post("/readings/", json=payload, headers=auth_headers)
        assert post_r.status_code == 200
        posted_id = post_r.json()["id"]

        latest_r = client.get("/readings/latest")
        assert latest_r.status_code == 200
        assert latest_r.json()["id"] == posted_id
        assert latest_r.json()["temperature"] == 24.7

    def test_ramp_order_oldest_id_is_lowest(self, seeded_client):
        """Ramp inserted oldest-first — ids[0] should be the smallest."""
        c, ids = seeded_client
        assert ids[0] == min(ids)
        assert ids[-1] == max(ids)

    def test_ramp_oldest_has_lowest_temperature(self, seeded_client):
        c, ids = seeded_client
        first_r = c.get(f"/readings/{ids[0]}").json()
        last_r  = c.get(f"/readings/{ids[-1]}").json()
        assert first_r["temperature"] < last_r["temperature"]

    def test_multiple_posts_all_persisted(self, client, auth_headers):
        """Post 5 readings and verify all 5 appear in GET /readings/."""
        for i in range(5):
            client.post("/readings/", json={
                "temperature": 20.0 + i,
                "humidity": 50.0,
                "pressure": 101000,
            }, headers=auth_headers)
        r = client.get("/readings/")
        assert len(r.json()) == 5
