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


