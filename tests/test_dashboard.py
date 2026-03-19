"""
test_dashboard.py — browser-level tests for the weather station dashboard.

Uses Playwright to load index.html in a real browser, intercept all API calls,
and inject mock responses derived from the same RAMP_DATA used in the API tests.
This keeps the two test layers in sync — if the ramp changes, both layers reflect it.

Setup (one-time):
    pip install pytest-playwright
    playwright install chromium

Run:
    pytest tests/test_dashboard.py -v
"""

import re
import threading
import functools
import http.server
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from conftest import RAMP_DATA, RAMP_LATEST_TEMP, RAMP_LATEST_HUM

# ---------------------------------------------------------------------------
# Derive mock API payloads from the same ramp used in API tests
# ---------------------------------------------------------------------------

# /readings/latest — the most recent ramp point
MOCK_LATEST = {
    "id": 10,
    "temperature": RAMP_LATEST_TEMP,
    "humidity": RAMP_LATEST_HUM,
    "pressure": 101000,
    "reboot_flag": None,
    "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

# /readings/history — full ramp, newest first (matches API ordering)
MOCK_HISTORY = [
    {
        "id": i + 1,
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "pressure": row["pressure"],
        "reboot_flag": row["reboot_flag"],
        "timestamp": row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for i, row in enumerate(reversed(RAMP_DATA))
]

# /summaries/ — one synthetic daily summary
MOCK_SUMMARY = [
    {
        "date": "2026-03-13",
        "avg_temp": 20.4,
        "avg_humidity": 55.4,
        "avg_pressure": 101000,
        "reboot_count": 1,
    }
]

# Stale timestamp — 10 minutes old, enough to trigger "offline"
MOCK_LATEST_STALE = {
    **MOCK_LATEST,
    "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
}


# ---------------------------------------------------------------------------
# Local HTTP server fixture — serves static/ over HTTP so Playwright can
# intercept fetch() calls (file:// doesn't support route interception).
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent.parent / "static"


@pytest.fixture(scope="session")
def static_server():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(STATIC_DIR),
    )
    server = http.server.HTTPServer(("localhost", 8999), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://localhost:8999"
    server.shutdown()


# ---------------------------------------------------------------------------
# Helper — register all three mock routes on a page
# ---------------------------------------------------------------------------

def _mock_all_routes(page: Page, latest=MOCK_LATEST):
    """Intercept all three API endpoints and return mock JSON."""
    page.route("**/readings/latest",          lambda r: r.fulfill(json=latest))
    page.route("**/readings/history**",        lambda r: r.fulfill(json=MOCK_HISTORY))
    page.route("**/summaries/**",              lambda r: r.fulfill(json=MOCK_SUMMARY))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardLayout:
    """Page loads and all structural elements are present."""

    def test_page_has_correct_title(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page).to_have_title("Sensor Data Dashboard")

    def test_stat_cards_are_visible(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#latest-temp")).to_be_visible()
        expect(page.locator("#latest-hum")).to_be_visible()

    def test_chart_canvas_is_present(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#sensorChart")).to_be_visible()

    def test_summary_table_is_present(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#summary-body")).to_be_visible()


class TestLatestReadings:
    """Stat cards display the correct values from /readings/latest."""

    def test_temperature_card_shows_latest_ramp_value(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#latest-temp")).to_have_text(f"{RAMP_LATEST_TEMP:.1f}°C")

    def test_humidity_card_shows_latest_ramp_value(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#latest-hum")).to_have_text(f"{RAMP_LATEST_HUM:.1f}%")


class TestStatusIndicator:
    """Status pill reflects whether the Pico is online or offline."""

    def test_recent_timestamp_shows_online(self, page: Page, static_server):
        _mock_all_routes(page, latest=MOCK_LATEST)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#status-text")).to_have_text("pico online")

    def test_status_dot_has_online_class_when_fresh(self, page: Page, static_server):
        _mock_all_routes(page, latest=MOCK_LATEST)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        dot = page.locator("#status-dot")
        expect(dot).to_have_class(re.compile(r"online"))

    def test_stale_timestamp_shows_offline(self, page: Page, static_server):
        _mock_all_routes(page, latest=MOCK_LATEST_STALE)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#status-text")).to_have_text("pico offline")

    def test_status_dot_has_offline_class_when_stale(self, page: Page, static_server):
        _mock_all_routes(page, latest=MOCK_LATEST_STALE)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        dot = page.locator("#status-dot")
        expect(dot).to_have_class(re.compile(r"offline"))

    def test_last_updated_text_is_shown(self, page: Page, static_server):
        _mock_all_routes(page, latest=MOCK_LATEST)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        updated = page.locator("#last-updated")
        expect(updated).not_to_be_empty()


class TestDailySummary:
    """Weekly summary table renders the mock summary row correctly."""

    def test_summary_row_shows_avg_temp(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#summary-body")).to_contain_text(
            f"{MOCK_SUMMARY[0]['avg_temp']:.1f}°C"
        )

    def test_summary_row_shows_avg_humidity(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#summary-body")).to_contain_text(
            f"{MOCK_SUMMARY[0]['avg_humidity']:.1f}%"
        )

    def test_summary_row_shows_reboot_count(self, page: Page, static_server):
        _mock_all_routes(page)
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#summary-body")).to_contain_text(
            str(MOCK_SUMMARY[0]["reboot_count"])
        )

    def test_empty_summaries_shows_waiting_message(self, page: Page, static_server):
        page.route("**/readings/latest",  lambda r: r.fulfill(json=MOCK_LATEST))
        page.route("**/readings/history**", lambda r: r.fulfill(json=MOCK_HISTORY))
        page.route("**/summaries/**",     lambda r: r.fulfill(json=[]))
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#summary-body")).to_contain_text("No summary data available")

class TestApiOffline:
    """Dashboard degrades gracefully when the API is unreachable."""

    def test_offline_api_shows_offline_status(self, page: Page, static_server):
        # Abort all API requests to simulate a dead server
        page.route("**iot-ingestion-api.onrender.com/**", lambda r: r.abort())
        page.goto(f"{static_server}/index.html", wait_until="networkidle")
        expect(page.locator("#status-text")).to_have_text("api offline")