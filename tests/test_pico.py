"""
test_pico.py — schema validation and Pico W session simulation.

Covers:
- Malformed payloads (missing fields, wrong types, nulls, empty body)
- Extra unknown fields ignored by Pydantic
- Realistic Pico posting sequence end-to-end
"""

import pytest


# ===========================================================================
# Schema validation
# ===========================================================================

class TestSchemaValidation:
    def test_missing_temperature_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "humidity": 50.0, "pressure": 101000
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_missing_humidity_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": 22.0, "pressure": 101000
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_missing_pressure_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": 22.0, "humidity": 50.0
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_temperature_as_string_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": "hot", "humidity": 50.0, "pressure": 101000
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_humidity_as_string_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": 22.0, "humidity": "wet", "pressure": 101000
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_pressure_as_string_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": 22.0, "humidity": 50.0, "pressure": "high"
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_empty_body_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={}, headers=auth_headers)
        assert r.status_code == 422

    def test_null_required_field_returns_422(self, client, auth_headers):
        r = client.post("/readings/", json={
            "temperature": None, "humidity": 50.0, "pressure": 101000
        }, headers=auth_headers)
        assert r.status_code == 422

    def test_extra_unknown_fields_are_ignored(self, client, auth_headers):
        """
        Pydantic ignores unknown fields by default.
        Useful for forward compatibility — Pico firmware can add fields
        without breaking the API.
        """
        r = client.post("/readings/", json={
            "temperature": 22.0,
            "humidity": 50.0,
            "pressure": 101000,
            "unknown_sensor": "some_value",
            "firmware_version": "1.2.3",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert "unknown_sensor" not in r.json()
        assert "firmware_version" not in r.json()


# ===========================================================================
# Pico W session simulation
# ===========================================================================

class TestPicoSession:
    def test_pico_session_simulation(self, client, auth_headers):
        """
        Simulates a realistic Pico W posting sequence end-to-end:

          1. Boot reading — includes reboot_flag=True
          2. Five steady readings — no reboot flag, slight temperature ramp
          3. /readings/latest confirms the last posted value
          4. Total count is correct (1 boot + 5 steady = 6)
          5. Exactly one reboot flag recorded across the session

        This mirrors what the physical device actually does on power-on.
        If this test fails, the Pico's data is likely not reaching the DB
        correctly end-to-end.
        """
        # 1. Boot
        boot = client.post("/readings/", json={
            "temperature": 21.0,
            "humidity":    54.0,
            "pressure":    101000,
            "reboot_flag": True,
        }, headers=auth_headers)
        assert boot.status_code == 200
        assert boot.json()["reboot_flag"] == True

        # 2. Steady readings
        last_payload = None
        for i in range(1, 6):
            last_payload = {
                "temperature": round(21.0 + i * 0.1, 1),
                "humidity":    round(54.0 + i * 0.1, 1),
                "pressure":    101000,
            }
            r = client.post("/readings/", json=last_payload, headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["reboot_flag"] is None

        # 3. Latest matches last posted
        latest = client.get("/readings/latest").json()
        assert latest["temperature"] == last_payload["temperature"]
        assert latest["humidity"]    == last_payload["humidity"]
        assert latest["reboot_flag"] is None

        # 4. Total count
        all_readings = client.get("/readings/").json()
        assert len(all_readings) == 6

        # 5. Exactly one reboot
        reboots = [r for r in all_readings if r["reboot_flag"] is not None]
        assert len(reboots) == 1
