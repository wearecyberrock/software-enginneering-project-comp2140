
"""Unit & Acceptance Tests for F-04 Customer Interface Search (Ashaya Watts)."""

from datetime import date
import pytest
from app import create_app
from shared.config import TestConfig
from shared.database import db
from shared.models import Vehicle, Shipment


# Create sample inventory for testing.
@pytest.fixture
def client():
    app = create_app(TestConfig)

    with app.app_context():

        records = [
            ("Toyota", "Corolla", "Arrived", None, 10000),
            ("Toyota", "Corolla", "In Transit", date(2026, 12, 1), 12500),
            ("Toyota", "Camry", "Arrived", None, 14000),
            ("Honda", "Civic", "Arrived", None, 11000),
            ("Honda", "Accord", "Arrived", None, 13000)
        ]

        for index, (make, model, status, eta, cost) in enumerate(records, 1):

            vehicle = Vehicle(
                make=make,
                model=model,
                year=2020,
                color="White",
                mileage_km=40000,
                engine_cc=1500,
                base_foreign_price=cost,
                deposit_paid=True
            )

            vehicle.shipment = Shipment(
                bill_of_lading=f"F04-TEST-{index}",
                status=status,
                eta_date=eta
            )

            db.session.add(vehicle)

        db.session.commit()

        yield app.test_client()


# TC-04.01 - TS-1 [AC-1]: Positive test
def test_ts1_search_filters_by_model(client):

    response = client.get("/api/public/vehicles?q=Corolla")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2

    # Check that only matching models are returned.
    for vehicle in vehicles:
        assert vehicle["model"].lower() == "corolla"

    # Check that available and upcoming vehicles are returned.
    statuses = [vehicle["availability"] for vehicle in vehicles]

    assert "Available Now" in statuses
    assert "Upcoming Arrival" in statuses


# TC-04.02 - TS-1 [AC-1]: Positive test
def test_ts1_search_filters_by_make_and_model(client):

    # Search by make.
    response = client.get("/api/public/vehicles?q=Honda")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2

    for vehicle in vehicles:
        assert vehicle["make"].lower() == "honda"

    models = [vehicle["model"] for vehicle in vehicles]

    assert "Civic" in models
    assert "Accord" in models

    # Search by make and model.
    response = client.get("/api/public/vehicles?q=Honda+Civic")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 1
    assert vehicles[0]["make"].lower() == "honda"
    assert vehicles[0]["model"].lower() == "civic"


# TC-04.03 - TS-2 [AC-1]: Negative test
def test_ts2_nonexistent_vehicle_search(client):

    response = client.get("/api/public/vehicles?q=XYZ123")

    assert response.status_code == 200
    assert response.get_json() == []

    # Check that the customer page displays the correct message.
    response = client.get("/browse?q=XYZ123")

    assert response.status_code == 200
    assert b"No matching vehicles found" in response.data


# TC-04.04 - TS-3 [AC-2]: Positive test
def test_ts3_internal_financial_data_not_exposed(client):

    response = client.get("/api/public/vehicles?q=Corolla")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2

    upcoming_found = False

    for vehicle in vehicles:

        # Check that the upcoming vehicle has the correct ETA.
        if vehicle["availability"] == "Upcoming Arrival":
            upcoming_found = True

            assert vehicle["estimated_arrival"] == "2026-12-01"

            detail = client.get(f"/vehicle/{vehicle['id']}")

            assert detail.status_code == 200
            assert b"2026-12-01" in detail.data

        # Check that internal information is excluded.
        assert "base_foreign_price" not in vehicle
        assert "base_currency" not in vehicle
        assert "bill_of_lading" not in vehicle
        assert "deposit_paid" not in vehicle
        assert "internal_purchasing_cost" not in vehicle

    assert upcoming_found


# TC-04.05 - TS-4 [AC-2]: Data privacy test
def test_ts4_restricted_financial_data_access(client):

    response = client.get("/api/public/vehicles?q=Corolla")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2

    restricted_fields = [
        "base_foreign_price",
        "base_currency",
        "bill_of_lading",
        "deposit_paid",
        "internal_purchasing_cost"
    ]

    for vehicle in vehicles:

        # Verify that the public response excludes restricted fields.
        for field in restricted_fields:
            assert field not in vehicle

        # Check the public vehicle detail page.
        detail = client.get(f"/vehicle/{vehicle['id']}")

        assert detail.status_code == 200

        for field in restricted_fields:
            assert field.encode() not in detail.data

        assert b"Internal Purchasing Cost" not in detail.data
