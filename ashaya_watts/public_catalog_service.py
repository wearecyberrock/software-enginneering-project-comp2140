"""F-04 Service: Public Inventory Filtering with Strict View Restriction (SR-3)."""

from datetime import date

from flask import current_app

from shared.database import db
from shared.models import Shipment, Vehicle
from shared.validators import sanitize_search_query


def load_demo_inventory():
    """Add sample vehicles to the local F-04 demonstration database."""
    if current_app.config.get("SQLALCHEMY_DATABASE_URI") != "sqlite:///f04_demo.db":
        return

    records = [
        ("Toyota", "Corolla", "Arrived", None, 10000),
        ("Toyota", "Corolla", "In Transit", date(2026, 12, 1), 12500),
        ("Toyota", "Camry", "Arrived", None, 14000),
        ("Honda", "Civic", "Arrived", None, 11000),
        ("Honda", "Accord", "Arrived", None, 13000),
    ]

    vehicles_added = False

    for index, (make, model, status, eta, cost) in enumerate(records, 1):
        reference = f"F04-DEMO-{index}"
        existing_shipment = Shipment.query.filter_by(
            bill_of_lading=reference
        ).first()

        if existing_shipment is not None:
            continue

        vehicle = Vehicle(
            make=make,
            model=model,
            year=2020,
            color="White",
            mileage_km=40000,
            engine_cc=1500,
            base_foreign_price=cost,
            deposit_paid=True,
        )

        vehicle.shipment = Shipment(
            bill_of_lading=reference,
            status=status,
            eta_date=eta,
        )

        db.session.add(vehicle)
        vehicles_added = True

    if vehicles_added:
        db.session.commit()


def serialize_public_vehicle(vehicle: Vehicle) -> dict:
    """Return only customer-safe vehicle information."""
    return {
        "id": vehicle.id,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "category": vehicle.category,
        "color": vehicle.color,
        "mileage_km": vehicle.mileage_km,
        "engine_cc": vehicle.engine_cc,
        "features": vehicle.features,
        "photo_urls": vehicle.photo_urls,
        "availability": (
            "Available Now"
            if vehicle.shipment and vehicle.shipment.status == "Arrived"
            else "Upcoming Arrival"
        ),
        "estimated_arrival": (
            vehicle.shipment.eta_date.isoformat()
            if vehicle.shipment and vehicle.shipment.eta_date
            else None
        ),
    }


def search_public_inventory(raw_query: str = "") -> list[dict]:
    """Filter public inventory by make and model."""
    load_demo_inventory()
    clean_q = sanitize_search_query(raw_query)

    if raw_query.strip() and not clean_q:
        return []

    q = Vehicle.query.filter_by(
        is_deleted=False,
        deposit_paid=True,
    )

    if clean_q:
        for term in clean_q.split():
            term = term.replace("\\", "\\\\")
            term = term.replace("%", "\\%").replace("_", "\\_")
            like = f"%{term}%"

            q = q.filter(
                Vehicle.make.ilike(like, escape="\\")
                | Vehicle.model.ilike(like, escape="\\")
            )

    return [serialize_public_vehicle(vehicle) for vehicle in q.all()]


def get_public_vehicle(vehicle_id: int) -> dict | None:
    """Retrieve public details for a single vehicle."""
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        is_deleted=False,
        deposit_paid=True,
    ).first()

    return serialize_public_vehicle(vehicle) if vehicle else None


