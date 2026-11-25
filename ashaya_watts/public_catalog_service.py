
"""F-04 Service: Public Inventory Filtering with Strict View Restriction (SR-3)."""

from shared.models import Vehicle
from shared.validators import sanitize_search_query


def serialize_public_vehicle(vehicle: Vehicle) -> dict:
    """
    Return only customer-safe vehicle information.
    Internal purchasing costs and other sensitive data are excluded.
    """
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
    """
    Filter available and upcoming vehicles by make and model.
    Return only information that customers are allowed to view.
    """
    clean_q = sanitize_search_query(raw_query)

    # Prevent invalid searches from returning the entire inventory.
    if raw_query.strip() and not clean_q:
        return []

    # Only include non-deleted vehicles with paid deposits.
    q = Vehicle.query.filter_by(
        is_deleted=False,
        deposit_paid=True
    )

    # Allow searches by make, model or both.
    if clean_q:
        for term in clean_q.split():
            term = term.replace("\\", "\\\\")
            term = term.replace("%", "\\%").replace("_", "\\_")
            like = f"%{term}%"

            q = q.filter(
                (Vehicle.make.ilike(like, escape="\\")) |
                (Vehicle.model.ilike(like, escape="\\"))
            )

    # Return matching vehicles with public information only.
    return [serialize_public_vehicle(v) for v in q.all()]


def get_public_vehicle(vehicle_id: int) -> dict | None:
    """
    Retrieve vehicle details without exposing internal information.
    """
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        is_deleted=False,
        deposit_paid=True
    ).first()

    return serialize_public_vehicle(vehicle) if vehicle else None


