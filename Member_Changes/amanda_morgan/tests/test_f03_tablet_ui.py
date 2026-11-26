"""Unit & Acceptance Tests for F-03 Mobile Portability Access (Amanda Morgan).

Part 1 needs no database (view helpers, templates, CSS).
Part 2 runs the real routes against an in-memory SQLite database.
Run with:  pytest amanda_morgan/tests
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template

from amanda_morgan import amanda_bp
from amanda_morgan.vehicle_view import (
    PLACEHOLDER_PHOTO,
    build_vehicle_view,
    format_mileage,
    parse_features,
    parse_photo_urls,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLET_CSS = REPO_ROOT / "amanda_morgan" / "static" / "tablet.css"


def make_vehicle(**overrides):
    """A stand-in for shared.models.Vehicle (same attribute names, no database)."""
    data = dict(
        id=1, make="Toyota", model="Corolla", year=2018, category="car", color="Wine Red",
        mileage_km=45000, engine_cc=1800, features="Sunroof, Keyless Entry, Alloy Rims",
        origin_country="Japan", photo_urls='["/p/1.jpg", "/p/2.jpg", "/p/3.jpg"]',
        shipment=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# Part 1: no database needed
# ---------------------------------------------------------------------------

def test_view_parse_photo_urls_handles_json_and_bad_data():
    assert parse_photo_urls('["/a.jpg", "/b.jpg"]') == ["/a.jpg", "/b.jpg"]
    assert parse_photo_urls("") == []
    assert parse_photo_urls(None) == []
    assert parse_photo_urls("[]") == []
    assert parse_photo_urls('{"not": "a list"}') == []
    assert parse_photo_urls("/only-one.jpg") == ["/only-one.jpg"]  # not JSON: tolerated, not a crash
    assert parse_photo_urls('["/ok.jpg", 5, null, "  "]') == ["/ok.jpg"]


def test_view_parse_features_handles_comma_text_and_json():
    assert parse_features("Sunroof, Keyless Entry, Alloy Rims") == ["Sunroof", "Keyless Entry", "Alloy Rims"]
    assert parse_features('["Sunroof", "Rims"]') == ["Sunroof", "Rims"]
    assert parse_features(None) == []
    assert parse_features("") == []


def test_view_format_mileage():
    assert format_mileage(45000) == "45,000 km"
    assert format_mileage(0) == "0 km"
    assert format_mileage(None) == "Not recorded"


def test_view_vehicle_without_photos_uses_placeholder_thumbnail():
    view = build_vehicle_view(make_vehicle(photo_urls=None))
    assert view["has_photos"] is False
    assert view["photos"] == []
    assert view["thumbnail"] == PLACEHOLDER_PHOTO


def test_view_includes_shipment_status_eta_and_price():
    shipment = SimpleNamespace(status="Delayed", eta_date=date(2026, 12, 1), is_deleted=False)
    view = build_vehicle_view(make_vehicle(shipment=shipment), estimated_price_jmd=Decimal("3750000.5"))
    assert view["shipment_status"] == "Delayed"
    assert view["status_class"] == "badge-delayed"
    assert view["eta_display"] == "Dec 01, 2026"
    assert view["estimated_price_display"] == "J$3,750,000.50"


def test_view_ignores_soft_deleted_shipment():
    shipment = SimpleNamespace(status="Arrived", eta_date=None, is_deleted=True)
    view = build_vehicle_view(make_vehicle(shipment=shipment))
    assert view["shipment_status"] is None
    assert view["estimated_price_display"] is None


@pytest.fixture()
def template_app():
    """Minimal Flask app that can render the F-03 templates (no database)."""
    app = Flask(__name__, template_folder=str(REPO_ROOT / "shared" / "templates"))
    app.register_blueprint(amanda_bp)
    return app


def test_template_profile_renders_mileage_specs_and_gallery(template_app):
    view = build_vehicle_view(make_vehicle())
    with template_app.test_request_context():
        html = render_template("vehicle_profile.html", vehicle=view)
    assert "2018 Toyota Corolla" in html
    assert "45,000 km" in html
    assert "Wine Red" in html
    assert "Keyless Entry" in html
    for url in ("/p/1.jpg", "/p/2.jpg", "/p/3.jpg"):
        assert url in html
    assert "Photo 1 of 3" in html
    assert 'id="gallery-prev"' in html and 'id="gallery-next"' in html
    assert "/amanda/static/gallery.js" in html


def test_template_profile_without_photos_shows_placeholder_not_gallery(template_app):
    view = build_vehicle_view(make_vehicle(photo_urls=None, make="Isuzu", model="Truck"))
    with template_app.test_request_context():
        html = render_template("vehicle_profile.html", vehicle=view)
    assert "No photos available" in html
    assert 'id="gallery"' not in html
    assert "45,000 km" in html  # specs and mileage still shown


def test_template_profile_escapes_html_in_vehicle_data(template_app):
    view = build_vehicle_view(make_vehicle(color="<script>alert(1)</script>"))
    with template_app.test_request_context():
        html = render_template("vehicle_profile.html", vehicle=view)
    assert "<script>alert(1)</script>" not in html


def test_template_dashboard_lists_vehicles_and_empty_state(template_app):
    cards = [build_vehicle_view(make_vehicle(id=7))]
    with template_app.test_request_context():
        html = render_template("tablet_dashboard.html", vehicles=cards, query="")
        empty = render_template("tablet_dashboard.html", vehicles=[], query="zzz")
    assert 'class="tablet-grid"' in html
    assert "/tablet/vehicle/7" in html
    assert "No vehicles match your search." in empty


def test_css_targets_tablet_range_and_touch_size():
    """TS-1 / AC-1: tablet breakpoint and 44px minimum tap target are in the stylesheet."""
    css = TABLET_CSS.read_text(encoding="utf-8")
    assert "@media (min-width: 768px) and (max-width: 1180px)" in css
    assert "--f03-tap: 44px" in css
    assert "scroll-snap-type" in css  # swipeable gallery


# ---------------------------------------------------------------------------
# Part 2: real routes + in-memory database
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_and_ids():
    from app import create_app
    from shared.config import TestConfig
    from shared.database import db
    from shared.models import Shipment, Vehicle

    application = create_app(TestConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()

        def vehicle(**kwargs):
            base = dict(
                category="car", engine_cc=1800, base_foreign_price=Decimal("10000.00"),
                base_currency="USD", deposit_paid=True, is_deleted=False,
            )
            base.update(kwargs)
            return Vehicle(**base)

        corolla = vehicle(
            make="Toyota", model="Corolla", year=2018, color="Wine Red", mileage_km=45000,
            features="Sunroof, Keyless Entry, Alloy Rims",
            photo_urls='["/p/1.jpg", "/p/2.jpg", "/p/3.jpg"]',
        )
        isuzu = vehicle(
            make="Isuzu", model="Truck", year=2016, category="truck", engine_cc=5200,
            color="White", mileage_km=98000, photo_urls=None,
        )
        deleted = vehicle(make="Honda", model="Civic", year=2017, is_deleted=True, mileage_km=61000)
        unpaid = vehicle(make="Nissan", model="Note", year=2019, deposit_paid=False, mileage_km=20000)
        db.session.add_all([corolla, isuzu, deleted, unpaid])
        db.session.commit()

        db.session.add(
            Shipment(vehicle_id=corolla.id, bill_of_lading="BOL-000", status="Delayed", eta_date=date(2026, 12, 1))
        )
        db.session.commit()

        ids = {"corolla": corolla.id, "isuzu": isuzu.id, "deleted": deleted.id, "unpaid": unpaid.id}

    client = application.test_client()
    with client.session_transaction() as staff:
        staff.update(user_id=1, user_role="sales_staff")
    yield client, ids

    with application.app_context():
        db.session.remove()
        db.drop_all()


def test_ts1_tablet_responsive_markup(app_and_ids):
    """TS-1 [AC-1]: the tablet page is responsive, touch-oriented markup (viewport + tablet CSS + grid)."""
    client, ids = app_and_ids
    html = client.get("/tablet/").get_data(as_text=True)
    assert 'name="viewport"' in html
    assert "/amanda/static/tablet.css" in html
    assert 'class="tablet-grid"' in html
    assert f"/tablet/vehicle/{ids['corolla']}" in html
    assert "Search" in html


def test_ts2_vehicle_profile_displays_mileage_and_photos(app_and_ids):
    """TS-2 [AC-2]: opening a vehicle profile shows mileage, specs and the photo gallery."""
    client, ids = app_and_ids
    response = client.get(f"/tablet/vehicle/{ids['corolla']}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "45,000 km" in html
    assert "Wine Red" in html
    assert "Sunroof" in html
    for url in ("/p/1.jpg", "/p/2.jpg", "/p/3.jpg"):
        assert url in html
    assert 'id="gallery"' in html
    assert "/amanda/static/gallery.js" in html
    assert "Delayed" in html and "Dec 01, 2026" in html  # shipment status and ETA are shown


def test_vehicle_without_photos_still_shows_specs(app_and_ids):
    client, ids = app_and_ids
    response = client.get(f"/tablet/vehicle/{ids['isuzu']}")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "No photos available" in html
    assert "98,000 km" in html


def test_unknown_vehicle_returns_404(app_and_ids):
    client, _ = app_and_ids
    assert client.get("/tablet/vehicle/99999").status_code == 404


def test_soft_deleted_and_unpaid_vehicles_are_hidden(app_and_ids):
    client, ids = app_and_ids
    listing = client.get("/tablet/").get_data(as_text=True)
    assert "Corolla" in listing and "Isuzu" in listing
    assert "Civic" not in listing  # soft-deleted (SRS 3.2)
    assert "Note" not in listing   # deposit not paid (F-02 gate)
    assert client.get(f"/tablet/vehicle/{ids['deleted']}").status_code == 404
    assert client.get(f"/tablet/vehicle/{ids['unpaid']}").status_code == 404


def test_search_filters_the_grid(app_and_ids):
    client, _ = app_and_ids
    html = client.get("/tablet/?q=corolla").get_data(as_text=True)
    assert "Corolla" in html and "Isuzu" not in html
    html = client.get("/tablet/?q=toyota 2018").get_data(as_text=True)
    assert "Corolla" in html
    html = client.get("/tablet/?q=zzzzz").get_data(as_text=True)
    assert "No vehicles match your search." in html


def test_search_input_is_sanitized(app_and_ids):
    client, _ = app_and_ids
    response = client.get("/tablet/", query_string={"q": "'; DROP TABLE vehicles; --"})
    assert response.status_code == 200
    assert "Corolla" in client.get("/tablet/").get_data(as_text=True)  # table still intact
