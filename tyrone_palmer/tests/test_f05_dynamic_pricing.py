"""Unit & Acceptance Tests for F-05 Dynamic Pricing Estimates."""

from decimal import Decimal

import pytest
from flask import Flask

from shared.config import TestConfig
from shared.database import db
from shared.models import Vehicle, FxRate, DutyTier

from tyrone_palmer import tyrone_bp
from tyrone_palmer.pricing_engine import (
    calculate_estimated_jmd_price,
)
from tyrone_palmer.rates_service import (
    update_fx_rate,
    update_duty_tier,
)


@pytest.fixture
def app():
    """Create an isolated application and test database."""

    app = Flask(__name__)
    app.config.from_object(TestConfig)

    db.init_app(app)
    app.register_blueprint(tyrone_bp)

    with app.app_context():

        db.create_all()

        db.session.add_all([
            FxRate(
                currency_code="USD",
                rate_to_jmd=Decimal("157.5000")
            ),

            DutyTier(
                id=1,
                label="Small Engine Car",
                vehicle_category="car",
                min_cc=0,
                max_cc=1500,
                duty_percentage=Decimal("45.00")
            ),

            DutyTier(
                id=2,
                label="Heavy Equipment",
                vehicle_category="heavy_equipment",
                min_cc=0,
                max_cc=None,
                duty_percentage=Decimal("25.00")
            ),

            Vehicle(
                id=1,
                make="Honda",
                model="Fit",
                year=2020,
                category="car",
                engine_cc=1500,
                base_foreign_price=Decimal("10000.00"),
                base_currency="USD",
                deposit_paid=True,
                is_deleted=False
            ),

            Vehicle(
                id=2,
                make="Kubota",
                model="Tractor",
                year=2019,
                category="heavy_equipment",
                engine_cc=3331,
                base_foreign_price=Decimal("10000.00"),
                base_currency="USD",
                deposit_paid=True,
                is_deleted=False
            )
        ])

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


# TS-1 / AC-1
def test_ts1_fx_rate_change_updates_estimated_price(app):
    """Verify price changes after updating the FX rate."""

    vehicle = db.session.get(Vehicle, 1)

    original_price = calculate_estimated_jmd_price(vehicle)

    assert original_price == Decimal("2283750.00")

    update_fx_rate("USD", "160.0000")

    updated_price = calculate_estimated_jmd_price(vehicle)

    assert updated_price == Decimal("2320000.00")
    assert updated_price > original_price


# TS-2 / AC-2
def test_ts2_small_engine_vs_heavy_equipment_duty(app):
    """Verify different vehicle categories receive correct duties."""

    small_car = db.session.get(Vehicle, 1)
    heavy_equipment = db.session.get(Vehicle, 2)

    car_price = calculate_estimated_jmd_price(small_car)

    equipment_price = calculate_estimated_jmd_price(
        heavy_equipment
    )

    assert car_price == Decimal("2283750.00")
    assert equipment_price == Decimal("1968750.00")
    assert car_price > equipment_price


def test_duty_percentage_update(app):
    """Verify updating a duty percentage changes the price."""

    vehicle = db.session.get(Vehicle, 1)

    update_duty_tier(1, "50.00")

    estimated_price = calculate_estimated_jmd_price(vehicle)

    assert estimated_price == Decimal("2362500.00")


def test_invalid_exchange_rate(app):
    """Reject negative and zero exchange rates."""

    with pytest.raises(ValueError):
        update_fx_rate("USD", "-10")

    with pytest.raises(ValueError):
        update_fx_rate("USD", "0")


def test_invalid_duty_percentage(app):
    """Reject negative duty percentages."""

    with pytest.raises(ValueError):
        update_duty_tier(1, "-5")


def test_missing_exchange_rate(app):
    """Handle a vehicle with an unsupported currency."""

    vehicle = db.session.get(Vehicle, 1)

    vehicle.base_currency = "XYZ"
    db.session.commit()

    with pytest.raises(ValueError):
        calculate_estimated_jmd_price(vehicle)


def test_missing_duty_tier(app):
    """Handle a vehicle without a matching duty category."""

    vehicle = db.session.get(Vehicle, 1)

    vehicle.category = "bus"
    db.session.commit()

    with pytest.raises(ValueError):
        calculate_estimated_jmd_price(vehicle)


def test_pricing_endpoint(app):
    """Verify the public endpoint returns the correct estimate."""

    client = app.test_client()

    response = client.get("/pricing/estimate/1")

    assert response.status_code == 200

    data = response.get_json()

    assert data["vehicle_id"] == 1
    assert data["currency"] == "JMD"
    assert data["status"] == "success"
    assert data["estimated_jmd_price"] == "2283750.00"

    # Ensure confidential purchasing information is not exposed.
    assert "base_foreign_price" not in data
    assert "base_currency" not in data
    assert "bill_of_lading" not in data


def test_nonexistent_vehicle(app):
    """Verify nonexistent vehicles return HTTP 404."""

    client = app.test_client()

    response = client.get("/pricing/estimate/999")

    assert response.status_code == 404


def test_deleted_vehicle(app):
    """Verify deleted vehicles are not publicly accessible."""

    vehicle = db.session.get(Vehicle, 1)

    vehicle.is_deleted = True
    db.session.commit()

    client = app.test_client()

    response = client.get("/pricing/estimate/1")

    assert response.status_code == 404


def test_unpaid_vehicle(app):
    """Verify inactive vehicles are not publicly accessible."""

    vehicle = db.session.get(Vehicle, 1)

    vehicle.deposit_paid = False
    db.session.commit()

    client = app.test_client()

    response = client.get("/pricing/estimate/1")

    assert response.status_code == 404


def test_unauthorized_rate_management(app):
    """Verify sales staff cannot modify pricing variables."""

    client = app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = 1
        session["user_role"] = "sales_staff"

    response = client.post("/admin/pricing-rates")

    assert response.status_code == 403
