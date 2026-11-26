"""F-01 Service: Shipment and Inventory Tracking by Bill of Lading."""

from shared.models import Shipment, Vehicle
from shared.validators import is_valid_bill_of_lading

DELAYED_STATUS = "Delayed"

# Shipment status -> badge class defined in resources/design/theme.css
STATUS_BADGE_CLASSES = {
    "Delayed": "badge-delayed",        # red - visibly flagged (F-01 AC-2)
    "In Transit": "badge-in-transit",  # amber
    "Arrived": "badge-arrived",        # green
    "Cleared": "badge-arrived",        # green
}


def find_shipment_by_bol(bill_of_lading: str):
    """Look up one shipment by its Bill of Lading (F-01 SR-1).

    Returns the Shipment, or None when the number is badly formatted, does not exist,
    or has been soft-deleted (SRS 3.2 - deleted records are hidden, not erased).
    A shipment whose vehicle was soft-deleted is hidden too.

    The Bill of Lading is checked with is_valid_bill_of_lading() first and then passed to
    the database as a parameter, never glued into the SQL text, so input such as
    "'; DROP TABLE shipments; --" cannot hurt the database (SRS 3.2 SQL injection protection).
    """
    if not is_valid_bill_of_lading(bill_of_lading):
        return None
    return (
        Shipment.query.join(Vehicle, Shipment.vehicle_id == Vehicle.id)
        .filter(
            Shipment.bill_of_lading == bill_of_lading.strip(),
            Shipment.is_deleted.is_(False),
            Vehicle.is_deleted.is_(False),
        )
        .first()
    )


def is_delayed(shipment) -> bool:
    """True when the saved status is 'Delayed' (F-01 SR-3)."""
    return shipment.status == DELAYED_STATUS


def build_tracking_view(shipment) -> dict:
    """Turn a Shipment row into the plain dict that track_shipment.html shows (F-01 SR-2).

    It only reads attributes, so it can be unit-tested with any object that looks like a
    Shipment (no database needed).
    """
    vehicle = getattr(shipment, "vehicle", None)
    eta = shipment.eta_date
    departure = getattr(shipment, "departure_date", None)
    updated = getattr(shipment, "updated_at", None)
    delayed = is_delayed(shipment)

    return {
        "bill_of_lading": shipment.bill_of_lading,
        "vehicle_title": f"{vehicle.year} {vehicle.make} {vehicle.model}" if vehicle else None,
        "status": shipment.status,
        "is_delayed": delayed,
        "badge_class": STATUS_BADGE_CLASSES.get(shipment.status, ""),
        "eta_display": eta.isoformat() if eta else "Not set yet",   # e.g. 2026-11-23
        "departure_display": departure.isoformat() if departure else None,
        "delay_reason": shipment.delay_reason if delayed else None,
        "updated_display": updated.strftime("%Y-%m-%d %H:%M UTC") if updated else None,
    }
