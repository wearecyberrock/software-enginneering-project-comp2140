"""F-04 Service: Public Inventory Filtering with Strict View Restriction (SR-3)."""

from datetime import date

from flask import current_app
from shared.photos import parse_photo_urls
from tyrone_palmer.pricing_engine import calculate_estimated_jmd_price

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
    shipment = vehicle.shipment
    if shipment and shipment.is_deleted:
        shipment = None
    availability = "Availability pending"
    if shipment:
        availability = "Available Now" if shipment.status in ("Arrived", "Cleared") else "Upcoming Arrival"
    try:
        price = str(calculate_estimated_jmd_price(vehicle))
    except ValueError:
        price = None
    return {
        "id": vehicle.id,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "category": vehicle.category,
        "color": vehicle.color,
        "mileage_km": vehicle.mileage_km,
        "engine_cc": vehicle.engine_cc,
        "transmission": vehicle.transmission,
        "fuel_type": vehicle.fuel_type,
        "features": vehicle.features,
        "photo_urls": parse_photo_urls(vehicle.photo_urls),
        "estimated_jmd_price": price,
        "availability": availability,
        "estimated_arrival": shipment.eta_date.isoformat() if shipment and shipment.eta_date else None,
    }


def search_public_inventory(raw_query: str = "", section=None, transmission="") -> list[dict]:
    """Filter public inventory by make and model."""
    load_demo_inventory()
    clean_q = sanitize_search_query(raw_query)

    if raw_query.strip() and not clean_q:
        return []

    q = Vehicle.active_inventory()

    if transmission:
        q = q.filter_by(transmission=transmission)
    if section:
        statuses = ("In Transit", "Delayed") if section == "upcoming" else ("Arrived", "Cleared")
        q = q.join(Vehicle.shipment).filter(Shipment.is_deleted.is_(False), Shipment.status.in_(statuses))

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
    vehicle = Vehicle.active_inventory().filter_by(id=vehicle_id).first()

    return serialize_public_vehicle(vehicle) if vehicle else None


