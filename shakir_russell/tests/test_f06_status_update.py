"""Unit & Acceptance Tests for F-06 Shipment Status & ETA Updating (Shakir Russell)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

from randre_fearon import randre_bp
from randre_fearon.tracking_service import find_shipment_by_bol
from shakir_russell import shakir_bp
from shakir_russell.status_update_service import (
    soft_delete_shipment,
    update_shipment_status,
)
from shared.config import TestConfig
from shared.database import db
from shared.models import Shipment, User, Vehicle

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def app():
    """Isolated Flask app with F-06 (Shakir) and F-01 (Randre) blueprints on in-memory SQLite."""
    flask_app = Flask(
        __name__,
        template_folder=str(REPO_ROOT / "shared" / "templates"),
    )
    flask_app.config.from_object(TestConfig)
    db.init_app(flask_app)
    flask_app.register_blueprint(shakir_bp)
    flask_app.register_blueprint(randre_bp)

    with flask_app.app_context():
        db.create_all()

        # Staff users covering RBAC roles
        users = [
            User(
                username="shakir_admin",
                email="shakir@karmanjahni.com",
                password_hash=generate_password_hash("StrongPass123!"),
                role="purchasing_manager",
                is_active=True,
            ),
            User(
                username="owner_user",
                email="owner@karmanjahni.com",
                password_hash=generate_password_hash("OwnerPass123!"),
                role="owner",
                is_active=True,
            ),
            User(
                username="sales_user",
                email="sales@karmanjahni.com",
                password_hash=generate_password_hash("SalesPass123!"),
                role="sales_staff",
                is_active=True,
            ),
            User(
                username="inactive_staff",
                email="inactive@karmanjahni.com",
                password_hash=generate_password_hash("Inactive123!"),
                role="internal_staff",
                is_active=False,
            ),
        ]
        db.session.add_all(users)

        # Sample vehicles & shipments
        tacoma = Vehicle(
            make="Toyota",
            model="Tacoma Pickup",
            year=2021,
            category="truck",
            color="Wine Red",
            mileage_km=42000,
            engine_cc=2700,
            base_foreign_price=Decimal("22500.00"),
            base_currency="USD",
            deposit_paid=True,
        )
        fit = Vehicle(
            make="Honda",
            model="Fit RS",
            year=2020,
            category="car",
            color="Deep Purple",
            mileage_km=31500,
            engine_cc=1500,
            base_foreign_price=Decimal("1450000.00"),
            base_currency="JPY",
            deposit_paid=True,
        )
        db.session.add_all([tacoma, fit])
        db.session.flush()

        db.session.add_all(
            [
                Shipment(
                    vehicle_id=tacoma.id,
                    bill_of_lading="KJ-BOL-2026-001",
                    status="In Transit",
                    eta_date=date(2026, 12, 30),
                    departure_date=date(2026, 11, 15),
                ),
                Shipment(
                    vehicle_id=fit.id,
                    bill_of_lading="KJ-BOL-2026-002",
                    status="Delayed",
                    eta_date=date(2026, 12, 18),
                    delay_reason="Port congestion",
                ),
            ]
        )
        db.session.commit()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


def login_as(client, username: str, password: str):
    """Helper to sign into the staff portal."""
    return client.post(
        "/staff/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Acceptance Tests (SRS F-06 TS-1 & TS-2)
# ---------------------------------------------------------------------------


def test_ts1_update_status_in_transit_to_arrived(app):
    """TS-1 [AC-1]: Authorized staff changes shipment status from In Transit to Arrived and commits to DB."""
    client = app.test_client()
    login_resp = login_as(client, "shakir_admin", "StrongPass123!")
    assert login_resp.status_code == 302

    response = client.post(
        "/shipments/update/KJ-BOL-2026-001",
        data={"status": "Arrived", "eta_date": "2026-12-30", "delay_reason": ""},
    )
    assert response.status_code == 200
    assert "Updated shipment KJ-BOL-2026-001" in response.get_data(as_text=True)

    with app.app_context():
        shipment = Shipment.query.filter_by(bill_of_lading="KJ-BOL-2026-001").first()
        assert shipment is not None
        assert shipment.status == "Arrived"


def test_ts2_eta_override_reflects_on_bol_search(app):
    """TS-2 [AC-2]: Entering a new ETA overwrites the old date and immediately appears on F-01 BoL search."""
    client = app.test_client()
    login_as(client, "shakir_admin", "StrongPass123!")

    response = client.post(
        "/shipments/manage",
        data={
            "bill_of_lading": "KJ-BOL-2026-001",
            "status": "Delayed",
            "eta_date": "2027-01-15",
            "delay_reason": "Tropical storm in shipping lane",
        },
    )
    assert response.status_code == 200

    # Immediately visible to F-01 tracking lookup (SR-3)
    with app.app_context():
        tracked = find_shipment_by_bol("KJ-BOL-2026-001")
        assert tracked is not None
        assert tracked.status == "Delayed"
        assert tracked.eta_date == date(2027, 1, 15)
        assert tracked.delay_reason == "Tropical storm in shipping lane"

    # Also verify F-01 route succeeds with updated record
    tracking_resp = client.get("/tracking/?bol=KJ-BOL-2026-001")
    assert tracking_resp.status_code == 200


# ---------------------------------------------------------------------------
# Service & Validation Tests
# ---------------------------------------------------------------------------


def test_service_updates_status_and_clears_delay_reason_when_cleared(app):
    with app.app_context():
        updated = update_shipment_status(
            bill_of_lading="KJ-BOL-2026-002",
            new_status="Cleared",
            new_eta=date(2026, 12, 20),
        )
        assert updated.status == "Cleared"
        assert updated.eta_date == date(2026, 12, 20)
        assert updated.delay_reason is None


def test_service_rejects_invalid_status_date_and_unknown_bol(app):
    with app.app_context():
        with pytest.raises(ValueError):
            update_shipment_status("KJ-BOL-2026-001", "Teleported")

        with pytest.raises(ValueError):
            update_shipment_status("KJ-BOL-2026-001", "In Transit", new_eta="not-a-date")

        with pytest.raises(LookupError):
            update_shipment_status("KJ-BOL-9999-999", "Arrived")


def test_sqli_input_in_bol_is_rejected_safely(app):
    client = app.test_client()
    login_as(client, "shakir_admin", "StrongPass123!")

    resp = client.post(
        "/shipments/manage",
        data={
            "bill_of_lading": "'; DROP TABLE shipments; --",
            "status": "Arrived",
            "eta_date": "2026-12-30",
        },
    )
    assert resp.status_code == 400
    assert "Invalid Bill of Lading format" in resp.get_data(as_text=True)

    with app.app_context():
        assert Shipment.query.count() == 2


# ---------------------------------------------------------------------------
# Security, Authentication & RBAC Tests (SRS §3.2)
# ---------------------------------------------------------------------------


def test_unauthenticated_user_redirected_to_staff_login(app):
    client = app.test_client()
    for path in ("/shipments/manage", "/shipments/update/KJ-BOL-2026-001"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/staff/login" in resp.headers["Location"]


def test_invalid_and_inactive_staff_login_rejected(app):
    client = app.test_client()
    bad_pw = login_as(client, "shakir_admin", "WrongPassword")
    assert bad_pw.status_code == 401
    assert "Invalid username or password" in bad_pw.get_data(as_text=True)

    inactive = login_as(client, "inactive_staff", "Inactive123!")
    assert inactive.status_code == 401


def test_rbac_blocks_sales_staff_and_allows_owner(app):
    client = app.test_client()
    login_as(client, "sales_user", "SalesPass123!")
    assert client.get("/shipments/manage").status_code == 403

    # Log in as owner (always permitted) using email
    login_resp = login_as(client, "owner@karmanjahni.com", "OwnerPass123!")
    assert login_resp.status_code == 302
    assert client.get("/shipments/manage").status_code == 200


def test_staff_logout_clears_session(app):
    client = app.test_client()
    login_as(client, "shakir_admin", "StrongPass123!")
    assert client.get("/shipments/manage").status_code == 200

    logout_resp = client.post("/staff/logout")
    assert logout_resp.status_code == 302
    assert client.get("/shipments/manage").status_code == 302


# ---------------------------------------------------------------------------
# Soft Delete Tests (SRS §3.2)
# ---------------------------------------------------------------------------


def test_soft_delete_hides_shipment_without_erasing_record(app):
    client = app.test_client()
    login_as(client, "shakir_admin", "StrongPass123!")

    del_resp = client.post("/shipments/delete/KJ-BOL-2026-002", follow_redirects=True)
    assert del_resp.status_code == 200
    html = del_resp.get_data(as_text=True)
    assert "Archived shipment KJ-BOL-2026-002" in html

    with app.app_context():
        # Row still exists in DB (soft-deleted, not permanently erased)
        row = Shipment.query.filter_by(bill_of_lading="KJ-BOL-2026-002").first()
        assert row is not None
        assert row.is_deleted is True
        assert row.deleted_at is not None

        # Hidden from F-01 tracking lookup and cannot be updated again
        assert find_shipment_by_bol("KJ-BOL-2026-002") is None
        with pytest.raises(LookupError):
            soft_delete_shipment("KJ-BOL-2026-002")
        with pytest.raises(LookupError):
            update_shipment_status("KJ-BOL-2026-002", "Arrived")
