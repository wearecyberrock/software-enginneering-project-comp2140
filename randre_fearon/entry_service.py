"""F-02 Service: Manual Data Entry for newly deposited vehicles.

The flow is split in two small steps so the route can check the photos in between:
    validate_vehicle_form(form_data)  -> cleaned dict, or raises EntryValidationError
    save_vehicle_record(cleaned)      -> saves Vehicle + Shipment together
log_new_vehicle(form_data) simply runs both steps in a row.
"""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from shared.database import db
from shared.models import Shipment, Vehicle
from shared.validators import is_valid_bill_of_lading

# Exact wording from the test plan (TC-02.04 / F-02 TS-4).
DEPOSIT_REQUIRED_MESSAGE = "Deposit confirmation required"

CATEGORY_CHOICES = [
    ("car", "Car / SUV"),
    ("pickup", "Pickup"),
    ("truck", "Truck"),
    ("bus", "Bus"),
    ("heavy_equipment", "Heavy equipment"),
    ("parts", "Parts"),
]
VALID_CATEGORIES = {value for value, _label in CATEGORY_CHOICES}
CURRENCY_CHOICES = ["USD", "JPY", "SGD", "THB", "EUR"]  # same codes as the fx_rates table
ORIGIN_COUNTRIES = ["Japan", "United States", "Singapore", "Thailand", "Europe"]

# vehicles.base_foreign_price is Numeric(12, 2): at most 10 digits before the decimal point.
MAX_PRICE = Decimal("9999999999.99")


class EntryValidationError(ValueError):
    """The Add Unit form was rejected.

    `errors` maps a form field name to its message, e.g. {"deposit_paid": "Deposit confirmation required"}.
    It is a ValueError, as the F-02 design asked for, so `except ValueError` also catches it.
    """

    def __init__(self, errors: dict):
        self.errors = dict(errors)
        super().__init__("; ".join(self.errors.values()))


# ---------------------------------------------------------------------------
# Small helpers that turn raw form text into clean Python values
# ---------------------------------------------------------------------------

def _text(value) -> str:
    """Any form value -> trimmed string ('' when missing)."""
    return "" if value is None else str(value).strip()


def _is_checked(value) -> bool:
    """HTML checkboxes send 'on' when ticked and nothing at all when not."""
    if isinstance(value, str):
        return value.strip().lower() in {"on", "true", "1", "yes"}
    return bool(value)


def _to_int(value):
    """'42,000' -> 42000. Returns None if it is not a whole number."""
    try:
        return int(_text(value).replace(",", ""))
    except ValueError:
        return None


def _to_money(value):
    """'$18,500' -> Decimal('18500.00'). Returns None if it is not a usable amount."""
    text = _text(value).replace("$", "").replace(",", "").replace(" ", "")
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            return None
        return amount.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _to_date(value):
    """'2026-12-30' -> date(2026, 12, 30). Blank -> None. Bad text raises ValueError."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    return date.fromisoformat(text) if text else None


def _to_photo_list(value) -> list:
    """Accepts a list, a JSON list string, or comma-separated links."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        try:
            items = json.loads(value)
        except (TypeError, ValueError):
            items = str(value).split(",")
        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list):
            items = []
    return [str(item).strip() for item in items if str(item).strip()]


# ---------------------------------------------------------------------------
# Step 1: validate
# ---------------------------------------------------------------------------

def validate_vehicle_specs(form_data):
    """Validate editable specifications for both new and existing vehicles."""
    errors = {}
    cleaned = {}

    # --- Required text: make, model ---------------------------------------
    for field, label, limit in (("make", "Make", 80), ("model", "Model", 100)):
        value = _text(form_data.get(field))
        if not value:
            errors[field] = f"{label} is required"
        elif len(value) > limit:
            errors[field] = f"{label} must be {limit} characters or fewer"
        cleaned[field] = value

    # --- Year ----------------------------------------------------------------
    max_year = date.today().year + 1
    year = _to_int(form_data.get("year"))
    if not _text(form_data.get("year")):
        errors["year"] = "Year is required"
    elif year is None or not 1900 <= year <= max_year:
        errors["year"] = f"Year must be a whole number between 1900 and {max_year}"
    cleaned["year"] = year

    # --- Category (defaults to car) -------------------------------------------
    category = _text(form_data.get("category")) or "car"
    if category not in VALID_CATEGORIES:
        errors["category"] = "Choose a category from the list"
    cleaned["category"] = category
    for field, choices in (("fuel_type", ("petrol", "diesel")), ("transmission", ("manual", "automatic"))):
        value = form_data.get(field)
        if category != "parts" and value not in choices:
            errors[field] = "Select " + " or ".join(choices)
        cleaned[field] = value if value in choices else None
    weight = None
    if category in ("pickup", "truck"):
        weight = _to_int(form_data.get("weight_kg"))
        if weight is None or not 1 <= weight <= 2147483647:
            errors["weight_kg"] = "Enter the vehicle weight in whole, positive kilograms"
    cleaned["weight_kg"] = weight

    # --- Optional text: colour, origin country, features -------------------
    for field, label, limit in (
        ("color", "Colour", 50),
        ("origin_country", "Country of origin", 50),
        ("features", "Features", 1000),
    ):
        value = _text(form_data.get(field))
        if len(value) > limit:
            errors[field] = f"{label} must be {limit} characters or fewer"
        cleaned[field] = value or None

    # --- Optional: mileage ------------------------------------------------------
    mileage_text = _text(form_data.get("mileage_km"))
    mileage = _to_int(mileage_text)
    if mileage_text and (mileage is None or not 0 <= mileage <= 9_999_999):
        errors["mileage_km"] = "Mileage must be a whole number of kilometres (0 or more)"
    cleaned["mileage_km"] = mileage if mileage_text else None

    # --- Required: engine size in cc (F-05 uses it to work out duty) ----------
    cc_text = _text(form_data.get("engine_cc"))
    engine_cc = _to_int(cc_text)
    if not cc_text:
        errors["engine_cc"] = "Engine size (cc) is required"
    elif engine_cc is None or not 1 <= engine_cc <= 100_000:
        errors["engine_cc"] = "Engine size must be a whole number of cc, such as 2800"
    cleaned["engine_cc"] = engine_cc

    return cleaned, errors


def validate_vehicle_form(form_data: dict) -> dict:
    """Check every field of the Add Unit form (F-02 SR-1, SR-2).

    Returns a cleaned dict ready for save_vehicle_record(). If anything is wrong it raises
    EntryValidationError listing ALL the problems at once, so the page can highlight every
    bad field in a single go (TC-02.02) and the deposit rule is never skipped (TC-02.04).
    """
    cleaned, errors = validate_vehicle_specs(form_data)

    # --- Required: purchase details (base foreign price + currency) ------------
    price_text = _text(form_data.get("base_foreign_price"))
    price = _to_money(price_text)
    if not price_text:
        errors["base_foreign_price"] = "Base price is required"
    elif price is None or not 0 < price <= MAX_PRICE:
        errors["base_foreign_price"] = "Base price must be an amount greater than 0, such as 18500"
    cleaned["base_foreign_price"] = price

    currency = (_text(form_data.get("base_currency")) or "USD").upper()
    if currency not in CURRENCY_CHOICES:
        errors["base_currency"] = "Choose a currency from the list"
    cleaned["base_currency"] = currency

    # --- Required: Bill of Lading (must be well formed and not used before) ----
    bol = _text(form_data.get("bill_of_lading"))
    if not bol:
        errors["bill_of_lading"] = "Bill of Lading number is required"
    elif not is_valid_bill_of_lading(bol):
        errors["bill_of_lading"] = (
            "Bill of Lading may only use letters, numbers, hyphens and underscores (3 to 64 characters)"
        )
    # The column is UNIQUE across ALL rows, so soft-deleted shipments count as "used" too.
    elif Shipment.query.filter_by(bill_of_lading=bol).first() is not None:
        errors["bill_of_lading"] = "That Bill of Lading number is already in the system"
    cleaned["bill_of_lading"] = bol

    # --- Optional: shipment dates ------------------------------------------------
    for field, label in (("departure_date", "Departure date"), ("eta_date", "Estimated arrival")):
        try:
            cleaned[field] = _to_date(form_data.get(field))
        except ValueError:
            errors[field] = f"{label} must be a valid date (YYYY-MM-DD)"
            cleaned[field] = None
    if cleaned["departure_date"] and cleaned["eta_date"] and cleaned["eta_date"] < cleaned["departure_date"]:
        errors["eta_date"] = "Estimated arrival cannot be before the departure date"

    # --- Optional: photo links (the route turns uploaded files into these) ------
    photo_urls = _to_photo_list(form_data.get("photo_urls"))
    if any(not url.startswith(("/", "http://", "https://")) for url in photo_urls):
        errors["photos"] = "Photo links must start with /, http:// or https://"
    cleaned["photo_urls"] = photo_urls

    # --- The deposit gate (F-02 SR-2 / AC-2) ----------------------------------------
    if not _is_checked(form_data.get("deposit_paid")):
        errors["deposit_paid"] = DEPOSIT_REQUIRED_MESSAGE

    if errors:
        raise EntryValidationError(errors)
    return cleaned


# ---------------------------------------------------------------------------
# Step 2: save
# ---------------------------------------------------------------------------

def save_vehicle_record(cleaned: dict) -> Vehicle:
    """Save the Vehicle and its linked Shipment in ONE commit (F-02 SR-3).

    Both rows are saved together or not at all, so there is never a vehicle without a
    shipment. The vehicle is saved as active (deposit_paid=True, is_deleted=False).
    """
    vehicle = Vehicle(
        make=cleaned["make"],
        model=cleaned["model"],
        year=cleaned["year"],
        category=cleaned["category"],
        transmission=cleaned["transmission"], fuel_type=cleaned["fuel_type"], weight_kg=cleaned["weight_kg"],
        color=cleaned["color"],
        mileage_km=cleaned["mileage_km"],
        engine_cc=cleaned["engine_cc"],
        features=cleaned["features"],
        origin_country=cleaned["origin_country"],
        photo_urls=json.dumps(cleaned["photo_urls"]),  # contract: JSON list, "[]" when none
        base_foreign_price=cleaned["base_foreign_price"],
        base_currency=cleaned["base_currency"],
        deposit_paid=True,
        is_deleted=False,
    )
    vehicle.shipment = Shipment(
        bill_of_lading=cleaned["bill_of_lading"],
        status="In Transit",
        eta_date=cleaned["eta_date"],
        departure_date=cleaned["departure_date"],
    )
    db.session.add(vehicle)
    try:
        db.session.commit()
    except IntegrityError:
        # Someone saved the same Bill of Lading a split second before us.
        db.session.rollback()
        raise EntryValidationError(
            {"bill_of_lading": "That Bill of Lading number is already in the system"}
        )
    except Exception:
        db.session.rollback()
        raise
    return vehicle


def log_new_vehicle(form_data: dict) -> Vehicle:
    """Validate the form and save the vehicle + shipment (F-02 SR-1, SR-2, SR-3).

    Raises EntryValidationError (a ValueError) if the deposit is not marked as paid (AC-2),
    or if any required detail is missing or invalid. Returns the saved Vehicle (AC-1).
    """
    return save_vehicle_record(validate_vehicle_form(form_data))
