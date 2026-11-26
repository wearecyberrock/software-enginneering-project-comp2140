"""F-03 view helpers: turn a Vehicle row into the plain dict the tablet templates render.

Nothing in this module touches the database, so it can be unit-tested with any object
that has the same attributes as shared.models.Vehicle.
"""

import json

from shared.photos import parse_photo_urls

PLACEHOLDER_PHOTO = "/resources/design/assets/placeholder-vehicle.svg"

CATEGORY_LABELS = {
    "car": "Car",
    "truck": "Truck",
    "bus": "Bus",
    "heavy_equipment": "Heavy equipment",
    "parts": "Parts",
}

# Shipment status -> badge class defined in resources/design/theme.css
STATUS_BADGE_CLASSES = {
    "Delayed": "badge-delayed",
    "In Transit": "badge-in-transit",
    "Arrived": "badge-arrived",
    "Cleared": "badge-arrived",
}

NOT_RECORDED = "Not recorded"


def parse_features(raw):
    """features is 'Sunroof, Keyless Entry, Alloy Rims' (or a JSON list, per the DB contract)."""
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        items = data if isinstance(data, list) else str(raw).split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def format_mileage(mileage_km):
    if mileage_km is None:
        return NOT_RECORDED
    return f"{mileage_km:,} km"


def format_category(category):
    if not category:
        return NOT_RECORDED
    return CATEGORY_LABELS.get(category, str(category).replace("_", " ").title())


def format_price_jmd(price):
    if price is None:
        return None
    return f"J${price:,.2f}"


def build_vehicle_view(vehicle, estimated_price_jmd=None):
    """Return the dict used by tablet_dashboard.html and vehicle_profile.html."""
    shipment = getattr(vehicle, "shipment", None)
    if shipment is not None and getattr(shipment, "is_deleted", False):
        shipment = None

    photos = parse_photo_urls(vehicle.photo_urls)
    eta = getattr(shipment, "eta_date", None) if shipment is not None else None

    return {
        "id": vehicle.id,
        "title": f"{vehicle.year} {vehicle.make} {vehicle.model}",
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "category": format_category(vehicle.category),
        "color": vehicle.color or NOT_RECORDED,
        "mileage_km": vehicle.mileage_km,
        "mileage_display": format_mileage(vehicle.mileage_km),
        "engine_display": f"{vehicle.engine_cc:,} cc" if vehicle.engine_cc else NOT_RECORDED,
        "origin_country": vehicle.origin_country or NOT_RECORDED,
        "features": parse_features(vehicle.features),
        "photos": photos,
        "has_photos": bool(photos),
        "thumbnail": photos[0] if photos else PLACEHOLDER_PHOTO,
        "shipment_status": shipment.status if shipment is not None else None,
        "status_class": STATUS_BADGE_CLASSES.get(shipment.status, "") if shipment is not None else "",
        "eta_display": eta.strftime("%b %d, %Y") if eta else None,
        "estimated_price_display": format_price_jmd(estimated_price_jmd),
    }
