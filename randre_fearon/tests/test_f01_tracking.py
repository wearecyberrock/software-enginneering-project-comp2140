"""Unit & Acceptance Tests for F-01 Shipment and Inventory Tracking (Randre Fearon).

How these tests line up with the Test Plan (TS = test scenario, TC = test case):
    TS-1 [AC-1]  TC-01.01  an existing Bill of Lading shows its status and ETA
    TS-2 [AC-1]  TC-01.02  a non-existent or blank Bill of Lading shows "Shipment not found"
    TS-3 [AC-2]  TC-01.03  a Delayed shipment is visibly highlighted
    TS-4 [AC-2]  (SRS)     an on-time (In Transit) shipment is NOT highlighted
The rest are extra checks for SRS 3.1 (speed) and 3.2 (security, soft delete).

Run with:  pytest randre_fearon/tests/test_f01_tracking.py -v
"""

import time
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from randre_fearon.tracking_service import build_tracking_view, find_shipment_by_bol
from shared.database import db
from shared.models import Shipment, Vehicle


def add_shipment(bol, status="In Transit", eta=None, make="Toyota", model="Hilux", year=2021,
                 delay_reason=None, shipment_deleted=False, vehicle_deleted=False):
    """Save one vehicle with one shipment (call inside `with flask_app.app_context()`)."""
    vehicle = Vehicle(
        make=make, model=model, year=year, category="truck", engine_cc=2800,
        base_foreign_price=Decimal("18500.00"), base_currency="USD",
        deposit_paid=True, is_deleted=vehicle_deleted,
    )
    vehicle.shipment = Shipment(
        bill_of_lading=bol, status=status, eta_date=eta,
        delay_reason=delay_reason, is_deleted=shipment_deleted,
    )
    db.session.add(vehicle)
    db.session.commit()


@pytest.fixture()
def tracked(flask_app):
    """The same sample shipments the Test Plan uses (BOL-000 on time, BOL-001 delayed)."""
    with flask_app.app_context():
        add_shipment("BOL-000", "In Transit", date(2026, 11, 23))
        add_shipment("BOL-001", "Delayed", date(2026, 12, 1), make="Honda", model="Fit",
                     year=2020, delay_reason="Tropical storm in the Pacific")
        add_shipment("BOL-002", "Arrived", date(2026, 11, 10), make="Kubota", model="M7060", year=2019)
        add_shipment("BOL-DELETED", "In Transit", date(2026, 12, 5), shipment_deleted=True)
        add_shipment("BOL-NOVEHICLE", "In Transit", date(2026, 12, 6), vehicle_deleted=True)
    return flask_app


# ---------------------------------------------------------------------------
# The four test scenarios from the SRS / Test Plan
# ---------------------------------------------------------------------------

def test_ts1_valid_bol_retrieves_status_and_eta(tracked, client):
    """TS-1 / TC-01.01: BOL-000 shows 'In Transit' and ETA 2026-11-23 (HTTP 200)."""
    response = client.get("/tracking/?bol=BOL-000")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="tracking-result"' in html
    assert "In Transit" in html
    assert "2026-11-23" in html
    assert "2021 Toyota Hilux" in html
    assert "BOL-000" in html

    # The service layer returns the same saved record the page is built from.
    with tracked.app_context():
        shipment = find_shipment_by_bol("BOL-000")
        assert shipment.status == "In Transit"
        assert shipment.eta_date == date(2026, 11, 23)


def test_ts2_invalid_bol_handled_gracefully(tracked, client):
    """TS-2 / TC-01.02: BOL-321 does not exist -> 'Shipment not found' (HTTP 200)."""
    response = client.get("/tracking/?bol=BOL-321")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Shipment not found" in html
    assert 'id="tracking-result"' not in html


def test_ts2_blank_bol_shows_shipment_not_found(tracked, client):
    """TS-2: searching with the box left empty also says 'Shipment not found'."""
    for url in ("/tracking/?bol=", "/tracking/?bol=%20%20%20"):
        html = client.get(url).get_data(as_text=True)
        assert "Shipment not found" in html
        assert 'id="tracking-result"' not in html


def test_ts3_delayed_status_is_highlighted(tracked, client):
    """TS-3 / TC-01.03: BOL-001 is Delayed -> red badge, banner and ETA 2026-12-01."""
    response = client.get("/tracking/?bol=BOL-001")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Delayed" in html
    assert "2026-12-01" in html
    assert "badge-delayed" in html                  # status badge from theme.css
    assert 'data-delayed="true"' in html
    assert "tracking-result-delayed" in html        # red edge on the whole result card
    assert 'id="delay-banner"' in html
    assert "Tropical storm in the Pacific" in html  # the reason staff can pass on to customers
    assert "eta-delayed" in html                    # ETA text is highlighted too


def test_ts4_on_time_status_is_not_highlighted(tracked, client):
    """TS-4: an In Transit (on time) shipment must NOT be marked or highlighted as Delayed."""
    html = client.get("/tracking/?bol=BOL-000").get_data(as_text=True)

    assert "In Transit" in html
    assert "badge-in-transit" in html
    assert "badge-delayed" not in html
    assert "tracking-result-delayed" not in html
    assert "delay-banner" not in html
    assert "Delayed" not in html
    assert 'data-delayed="false"' in html


def test_arrived_shipment_shows_green_badge(tracked, client):
    html = client.get("/tracking/?bol=BOL-002").get_data(as_text=True)
    assert "badge-arrived" in html and "badge-delayed" not in html


# ---------------------------------------------------------------------------
# Page behaviour
# ---------------------------------------------------------------------------

def test_first_visit_shows_search_box_but_no_error(tracked, client):
    html = client.get("/tracking/").get_data(as_text=True)
    assert 'name="bol"' in html
    assert "Shipment not found" not in html


def test_search_ignores_spaces_around_the_number(tracked, client):
    html = client.get("/tracking/?bol=%20BOL-000%20").get_data(as_text=True)
    assert 'id="tracking-result"' in html


def test_not_found_for_badly_formatted_number_explains_allowed_characters(tracked, client):
    html = client.get("/tracking/", query_string={"bol": "BOL 000!"}).get_data(as_text=True)
    assert "Shipment not found" in html
    assert "letters, numbers, hyphens" in html


def test_shipment_without_eta_says_not_set_yet(flask_app, client):
    with flask_app.app_context():
        add_shipment("BOL-NOETA", "In Transit", None)
    html = client.get("/tracking/?bol=BOL-NOETA").get_data(as_text=True)
    assert "Not set yet" in html


# ---------------------------------------------------------------------------
# SRS 3.2 security and soft delete
# ---------------------------------------------------------------------------

def test_soft_deleted_shipment_is_hidden(tracked, client):
    html = client.get("/tracking/?bol=BOL-DELETED").get_data(as_text=True)
    assert "Shipment not found" in html
    with tracked.app_context():
        assert find_shipment_by_bol("BOL-DELETED") is None
        assert Shipment.query.filter_by(bill_of_lading="BOL-DELETED").count() == 1  # kept, not erased


def test_shipment_of_soft_deleted_vehicle_is_hidden(tracked, client):
    html = client.get("/tracking/?bol=BOL-NOVEHICLE").get_data(as_text=True)
    assert "Shipment not found" in html


def test_sql_injection_attempt_is_harmless(tracked, client):
    """The text is validated and sent to the database as a parameter, so it cannot run as SQL."""
    for attack in ("'; DROP TABLE shipments; --", "BOL-000' OR '1'='1", "BOL-000 OR 1=1"):
        html = client.get("/tracking/", query_string={"bol": attack}).get_data(as_text=True)
        assert "Shipment not found" in html
        assert 'id="tracking-result"' not in html
    with tracked.app_context():
        assert Shipment.query.count() == 5  # table still there, nothing removed
    assert "In Transit" in client.get("/tracking/?bol=BOL-000").get_data(as_text=True)


def test_search_text_is_escaped_so_scripts_cannot_run(tracked, client):
    html = client.get("/tracking/", query_string={"bol": "<script>alert(1)</script>"}).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html


# ---------------------------------------------------------------------------
# SRS 3.1 performance: tracking data in under 3 seconds
# ---------------------------------------------------------------------------

def test_lookup_returns_in_under_three_seconds(flask_app, client):
    with flask_app.app_context():
        db.session.add_all(
            Vehicle(
                make="Toyota", model="Corolla", year=2020, category="car", engine_cc=1500,
                base_foreign_price=Decimal("9000.00"), base_currency="USD", deposit_paid=True,
                shipment=Shipment(bill_of_lading=f"BOL-{n:04d}", status="In Transit", eta_date=date(2026, 12, 30)),
            )
            for n in range(500)
        )
        db.session.commit()

    started = time.perf_counter()
    response = client.get("/tracking/?bol=BOL-0499")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert 'id="tracking-result"' in response.get_data(as_text=True)
    assert elapsed < 3.0


# ---------------------------------------------------------------------------
# build_tracking_view needs no database
# ---------------------------------------------------------------------------

def make_shipment(**overrides):
    data = dict(
        bill_of_lading="BOL-777", status="In Transit", eta_date=date(2026, 11, 23),
        departure_date=date(2026, 10, 20), delay_reason=None,
        updated_at=datetime(2026, 11, 20, 14, 5),
        vehicle=SimpleNamespace(year=2021, make="Toyota", model="Hilux"),
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_view_for_on_time_shipment():
    view = build_tracking_view(make_shipment())
    assert view["status"] == "In Transit"
    assert view["is_delayed"] is False
    assert view["badge_class"] == "badge-in-transit"
    assert view["eta_display"] == "2026-11-23"
    assert view["vehicle_title"] == "2021 Toyota Hilux"
    assert view["updated_display"] == "2026-11-20 14:05 UTC"


def test_view_for_delayed_shipment_flags_it_and_keeps_reason():
    view = build_tracking_view(make_shipment(status="Delayed", delay_reason="Port congestion"))
    assert view["is_delayed"] is True
    assert view["badge_class"] == "badge-delayed"
    assert view["delay_reason"] == "Port congestion"


def test_view_copes_with_missing_optional_data():
    view = build_tracking_view(make_shipment(eta_date=None, departure_date=None, updated_at=None, vehicle=None,
                                             status="Something New"))
    assert view["eta_display"] == "Not set yet"
    assert view["departure_display"] is None
    assert view["updated_display"] is None
    assert view["vehicle_title"] is None
    assert view["badge_class"] == ""
