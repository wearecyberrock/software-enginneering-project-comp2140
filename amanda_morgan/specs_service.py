"""F-03 Service: Retrieve vehicle specs, mileage, features, and photos for tablet view."""

from flask import current_app
from sqlalchemy import String, cast, or_

from amanda_morgan.vehicle_view import build_vehicle_view
from shared.models import Vehicle
from shared.validators import sanitize_search_query

# F-05 (Tyrone) supplies the estimated JMD price shown on the profile.
try:
    from tyrone_palmer.pricing_engine import calculate_estimated_jmd_price
except ImportError:  # pragma: no cover - only if F-05's folder is missing from a branch
    calculate_estimated_jmd_price = None


def _active_vehicles():
    """Vehicles that are live: deposit paid (F-02 gate) and not soft-deleted (SRS 3.2)."""
    return Vehicle.active_inventory()


def _estimated_price(vehicle):
    """F-05 estimate, or None while F-05 is unfinished or cannot price this vehicle.

    A pricing problem must never stop a salesperson from opening the specs page.
    """
    if calculate_estimated_jmd_price is None:
        return None
    try:
        return calculate_estimated_jmd_price(vehicle)
    except NotImplementedError:
        return None
    except Exception:  # noqa: BLE001 - keep the page usable, but leave a trace in the logs
        current_app.logger.warning("F-05 price estimate failed for vehicle %s", vehicle.id, exc_info=True)
        return None


def list_active_vehicles(query: str = ""):
    """Active vehicles for the tablet grid, optionally filtered by a search string.

    Every word in the search must match the make, model, colour or year, so
    "toyota corolla" and "red 2018" both work. Input is sanitized and the
    filters are parameterized (SRS 3.2 SQL injection protection).
    """
    q = _active_vehicles()
    for word in sanitize_search_query(query).split():
        like = f"%{word}%"
        q = q.filter(
            or_(
                Vehicle.make.ilike(like),
                Vehicle.model.ilike(like),
                Vehicle.color.ilike(like),
                cast(Vehicle.year, String).ilike(like),
            )
        )
    vehicles = q.order_by(Vehicle.make, Vehicle.model, Vehicle.year.desc()).all()
    return [build_vehicle_view(v) for v in vehicles]


def get_vehicle_profile(vehicle_id: int):
    """One active vehicle with parsed photos, mileage, colour, features, shipment status and
    the F-05 price estimate (SR-3, AC-2). Returns None if it does not exist or is not active."""
    vehicle = _active_vehicles().filter_by(id=vehicle_id).first()
    if vehicle is None:
        return None
    return build_vehicle_view(vehicle, estimated_price_jmd=_estimated_price(vehicle))
