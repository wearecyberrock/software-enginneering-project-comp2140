"""F-06 Service: Update transit status, override ETA, soft-delete shipments, and staff login."""

from datetime import date, datetime, timezone
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from shared.database import db
from shared.models import Shipment, User
from shared.validators import is_valid_bill_of_lading, sanitize_search_query

STATUS_OPTIONS = ("In Transit", "Delayed", "Arrived", "Cleared")
VALID_STATUSES = set(STATUS_OPTIONS)

STATUS_BADGE_CLASSES = {
    "In Transit": "badge-in-transit",
    "Delayed": "badge-delayed",
    "Arrived": "badge-arrived",
    "Cleared": "badge-cleared",
}


def parse_eta_date(eta_value: date | str | None) -> date | None:
    """Convert a YYYY-MM-DD string or date object into a date; None/blank returns None."""
    if eta_value is None:
        return None
    if isinstance(eta_value, datetime):
        return eta_value.date()
    if isinstance(eta_value, date):
        return eta_value
    text = str(eta_value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("ETA must be a valid date in YYYY-MM-DD format.") from exc


def list_active_shipments(bol_query: str = "") -> list[Shipment]:
    """Return active (non-deleted) shipments, optionally filtered by Bill of Lading."""
    query = Shipment.query.filter_by(is_deleted=False)
    cleaned = sanitize_search_query(bol_query)
    if cleaned:
        query = query.filter(Shipment.bill_of_lading.ilike(f"%{cleaned}%"))
    return query.order_by(Shipment.id.asc()).all()


def get_active_shipment(bill_of_lading: str) -> Shipment | None:
    """Look up a single active shipment by its Bill of Lading number."""
    if not is_valid_bill_of_lading(bill_of_lading):
        return None
    return Shipment.query.filter_by(
        bill_of_lading=bill_of_lading.strip(),
        is_deleted=False,
    ).first()


def update_shipment_status(
    bill_of_lading: str,
    new_status: str,
    new_eta: date | str | None = None,
    delay_reason: str | None = None,
) -> Shipment:
    """Update a shipment's transit status, ETA, and optional delay reason, then commit."""
    status = (new_status or "").strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Choose from: {', '.join(STATUS_OPTIONS)}.")

    bol = (bill_of_lading or "").strip()
    if not is_valid_bill_of_lading(bol):
        raise ValueError("Invalid Bill of Lading format.")

    shipment = Shipment.query.filter_by(bill_of_lading=bol, is_deleted=False).first()
    if shipment is None:
        raise LookupError(f"Active shipment '{bol}' was not found.")

    parsed_eta = parse_eta_date(new_eta)
    shipment.status = status
    if parsed_eta is not None:
        shipment.eta_date = parsed_eta

    if delay_reason is not None:
        cleaned_reason = delay_reason.strip()[:255]
        shipment.delay_reason = cleaned_reason or None
    elif status != "Delayed":
        shipment.delay_reason = None

    shipment.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return shipment


def soft_delete_shipment(bill_of_lading: str) -> Shipment:
    """Soft-delete an active shipment so history stays in the database (SRS §3.2)."""
    bol = (bill_of_lading or "").strip()
    if not is_valid_bill_of_lading(bol):
        raise ValueError("Invalid Bill of Lading format.")

    shipment = Shipment.query.filter_by(bill_of_lading=bol, is_deleted=False).first()
    if shipment is None:
        raise LookupError(f"Active shipment '{bol}' was not found.")

    now = datetime.now(timezone.utc)
    shipment.is_deleted = True
    shipment.deleted_at = now
    shipment.updated_at = now
    db.session.commit()
    return shipment


def authenticate_staff(identifier: str, password: str) -> User | None:
    """Verify staff username/email and password against active User records (SRS §3.2)."""
    login_id = (identifier or "").strip()
    if not login_id or not password:
        return None
    user = (
        User.query.filter(
            User.is_active.is_(True),
            or_(User.username == login_id, User.email == login_id),
        )
        .first()
    )
    if user is None or not check_password_hash(user.password_hash, password):
        return None
    return user
