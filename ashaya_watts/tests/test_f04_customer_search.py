
"""Unit & Acceptance Tests for F-04 Customer Interface Search (Ashaya Watts)."""

from datetime import date
import pytest
from app import create_app
from shared.config import TestConfig
from shared.database import db
from shared.models import Vehicle, Shipment


# Internal information that customers should not see.
RESTRICTED_FIELDS = [
    "base_foreign_price",
    "base_currency",
    "bill_of_lading",
    "deposit_paid",
    "internal_purchasing_cost"
]


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

        try:
            yield app.test_client()
        finally:
            db.session.remove()


# TC-04.01 - TS-1 [AC-1]
# Check that searching by model returns only matching vehicles.
def test_ts1_search_filters_by_model(client):

    response = client.get("/api/public/vehicles?q=Corolla")

    assert response.status_code == 200

    vehicles = response.get_json()

    # Exactly two Corollas should be returned.
    assert len(vehicles) == 2, "Expected exactly two Corollas"

    for vehicle in vehicles:
        assert vehicle["make"] == "Toyota"
        assert vehicle["model"] == "Corolla"

    # Check that both available and upcoming vehicles appear.
    statuses = {vehicle["availability"] for vehicle in vehicles}

    assert statuses == {"Available Now", "Upcoming Arrival"}

    # Check the customer inventory page.
    page = client.get("/browse?q=Corolla")

    assert page.status_code == 200
    assert b"Toyota Corolla" in page.data
    assert b"Toyota Camry" not in page.data

    print("\nTC-04.01 PASSED: Only matching Corollas were returned.")


# TC-04.02 - TS-1 [AC-1]
# Check make and model filtering.
def test_ts1_search_filters_by_make_and_model(client):

    # Search by make.
    response = client.get("/api/public/vehicles?q=Honda")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2, "Expected two Honda vehicles"

    models = {vehicle["model"] for vehicle in vehicles}

    assert models == {"Civic", "Accord"}

    for vehicle in vehicles:
        assert vehicle["make"] == "Honda"

    # Search by make and model.
    response = client.get("/api/public/vehicles?q=Honda+Civic")

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 1, "Expected only one Honda Civic"
    assert vehicles[0]["make"] == "Honda"
    assert vehicles[0]["model"] == "Civic"

    # Check the customer inventory page.
    page = client.get("/browse?q=Honda+Civic")

    assert page.status_code == 200
    assert b"Honda Civic" in page.data
    assert b"Honda Accord" not in page.data
    assert b"Toyota Camry" not in page.data

    print("\nTC-04.02 PASSED: Make and model filtering works correctly.")


# TC-04.03 - TS-2 [AC-1]
# Check searching for a nonexistent vehicle.
def test_ts2_nonexistent_vehicle_search(client):

    response = client.get("/api/public/vehicles?q=XYZ123")

    assert response.status_code == 200
    assert response.get_json() == []

    # Check the message displayed on the customer page.
    page = client.get("/browse?q=XYZ123")

    assert page.status_code == 200
    assert b"No matching vehicles found" in page.data

    print("\nTC-04.03 PASSED: No matching vehicles found message displayed.")


# TC-04.04 - TS-3 [AC-2]
# Check that the ETA is visible and purchasing costs are hidden.
def test_ts3_internal_financial_data_not_exposed(client):

    response = client.get("/api/public/vehicles?q=Corolla")

    assert response.status_code == 200

    vehicles = response.get_json()

    # Find the upcoming Corolla.
    upcoming = [
        vehicle for vehicle in vehicles
        if vehicle["availability"] == "Upcoming Arrival"
    ]

    assert len(upcoming) == 1

    vehicle = upcoming[0]

    # Check the exact ETA from the test plan.
    assert vehicle["estimated_arrival"] == "2026-12-01"

    # Check that internal information is excluded.
    for vehicle in vehicles:
        for field in RESTRICTED_FIELDS:
            assert field not in vehicle

    # Check the customer inventory page.
    page = client.get("/browse?q=Corolla")

    assert page.status_code == 200
    assert b"2026-12-01" in page.data

    # Check that the actual purchasing cost is hidden.
    assert b"12500" not in page.data
    assert b"12,500" not in page.data
    assert b"12500" not in response.data
    assert b"12,500" not in response.data

    print("\nTC-04.04 PASSED: Correct ETA displayed and purchasing cost hidden.")


# TC-04.05 - TS-4 [AC-2]
# Check unauthorized access to internal purchasing costs.
def test_ts4_restricted_financial_data_access(client):

    # Attempt to request restricted financial fields.
    response = client.get(
        "/api/public/vehicles?q=Corolla"
        "&fields=base_foreign_price,base_currency,"
        "bill_of_lading,deposit_paid,internal_purchasing_cost"
    )

    assert response.status_code == 200

    vehicles = response.get_json()

    assert len(vehicles) == 2

    for vehicle in vehicles:

        # Verify that restricted fields cannot be retrieved.
        for field in RESTRICTED_FIELDS:
            assert field not in vehicle

        # Check the public vehicle details page.
        detail = client.get(f"/vehicle/{vehicle['id']}")

        assert detail.status_code == 200

        for field in RESTRICTED_FIELDS:
            assert field.encode() not in detail.data

        # Verify that the actual internal costs are hidden.
        assert b"12500" not in detail.data
        assert b"12,500" not in detail.data
        assert b"10000" not in detail.data
        assert b"10,000" not in detail.data
        assert b"Internal Purchasing Cost" not in detail.data
        assert b"F04-TEST-" not in detail.data

    # Check the public API response.
    assert b"12500" not in response.data
    assert b"12,500" not in response.data
    assert b"10000" not in response.data
    assert b"10,000" not in response.data
    assert b"F04-TEST-" not in response.data

    print("\nTC-04.05 PASSED: Restricted financial information is inaccessible through the tested public routes.")

