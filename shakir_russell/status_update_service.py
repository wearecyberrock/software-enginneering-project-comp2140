"""
==============================================================================
INTRODUCTION — shakir_russell/status_update_service.py
==============================================================================
Author:      Shakir Russell (Student ID: 620181663)
Course:      COMP2140 — Introduction to Software Engineering
Feature:     F-06 Shipment Status & ETA Updating (SRS §2.3 & §3.2)

What this file does:
    This is the "service layer" (business logic) for F-06. Instead of putting
    all database code directly inside the web routes, we put helper functions
    here so the code is cleaner and much easier to test with pytest.

    Functions in this file:
    1. parse_eta_date()         — Checks and converts an ETA string to a Python date.
    2. find_active_shipment()   — Finds one active (non-deleted) shipment by BoL.
    3. get_all_active_shipments() — Gets all active shipments for the staff table.
    4. update_shipment_status() — Updates status, ETA, and delay reason in the DB.
    5. soft_delete_shipment()   — Hides a shipment (is_deleted=True) without erasing it.
    6. authenticate_staff()     — Checks staff username and hashed password for login.

Libraries used:
    - datetime (date, datetime, timezone): Python's built-in library for working
      with calendar dates (ETA) and UTC timestamps (updated_at, deleted_at).
    - werkzeug.security (check_password_hash): Security library installed with
      Flask that safely compares a plain-text password against a hashed password.

What this file pulls from the shared/group code:
    - `shared/database.py` -> `db`: The shared SQLAlchemy database object used
      by all 5 group members so every module reads/writes the same database.
    - `shared/models.py` -> `Shipment`, `Vehicle`, `User`: The agreed database
      table models shared across the whole team.
    - `shared/validators.py` -> `is_valid_bill_of_lading`: Shared helper that
      checks the Bill of Lading format to block SQL injection (SRS §3.2).
    - Connects with Randre's F-01 (`randre_fearon/tracking_service.py`) and
      Ashaya's F-04 (`ashaya_watts/public_catalog_service.py`): Because we
      commit updates straight to `db.session`, F-01 and F-04 see the new
      status and ETA immediately!
==============================================================================
"""

# Import date, datetime, and timezone from Python's built-in datetime library
from datetime import date, datetime, timezone

# Import check_password_hash from Werkzeug to safely verify hashed staff passwords
from werkzeug.security import check_password_hash

# Pull the shared SQLAlchemy database connection from the team's shared/ folder
from shared.database import db

# Pull the shared database table models (Shipment, Vehicle, User) from shared/models.py
from shared.models import Shipment, User, Vehicle

# Pull the shared Bill of Lading format checker from shared/validators.py (protects against SQLi)
from shared.validators import is_valid_bill_of_lading

# Variable `STATUS_CHOICES`: ordered list of valid statuses shown in the HTML dropdown (F-06 SR-1)
STATUS_CHOICES = ["In Transit", "Delayed", "Arrived", "Cleared"]

# Variable `VALID_STATUSES`: a Python set of allowed statuses for fast validation checks
VALID_STATUSES = set(STATUS_CHOICES)

# Variable `STATUS_BADGE_CLASSES`: maps each status text to its CSS badge class in resources/design/theme.css
STATUS_BADGE_CLASSES = {
    "In Transit": "badge-in-transit",  # Amber badge style from theme.css
    "Delayed": "badge-delayed",        # Red highlighted badge style from theme.css
    "Arrived": "badge-arrived",        # Green badge style from theme.css
    "Cleared": "badge-arrived",        # Green badge style from theme.css
}


def parse_eta_date(eta_value):
    """Convert an ETA input (date object, 'YYYY-MM-DD' string, or blank) into a date or None."""
    # If nothing was provided (None or empty string), return None (meaning do not change ETA)
    if eta_value is None or eta_value == "":
        return None

    # If the caller already passed a Python date object (e.g., from a unit test), return it as-is
    if isinstance(eta_value, date) and not isinstance(eta_value, datetime):
        return eta_value

    # If the caller passed a string from an HTML <input type="date">, remove extra spaces first
    if isinstance(eta_value, str):
        # Variable `cleaned_date`: the date string with leading/trailing spaces removed
        cleaned_date = eta_value.strip()
        # If the string is empty after stripping spaces, treat it as no ETA entered
        if not cleaned_date:
            return None
        try:
            # Convert 'YYYY-MM-DD' text into a real Python date object
            return date.fromisoformat(cleaned_date)
        except ValueError as exc:
            # Raise a clear error message if the date is not a real YYYY-MM-DD date
            raise ValueError("Invalid ETA date format. Please use YYYY-MM-DD.") from exc

    # If some other unexpected type was passed, raise a clear ValueError
    raise ValueError("ETA must be a valid date.")


def find_active_shipment(bill_of_lading: str):
    """Look up one active (non-deleted) Shipment by its Bill of Lading number."""
    # Check the BoL format using shared/validators.py before touching the database (SRS §3.2 SQLi safety)
    if not is_valid_bill_of_lading(bill_of_lading):
        # Return None immediately if the BoL is blank or contains unsafe characters
        return None

    # Variable `clean_bol`: trimmed Bill of Lading string ready for a parameterized SQL query
    clean_bol = bill_of_lading.strip()

    # Query the shared `shipments` table joined with `vehicles`
    # Filter out soft-deleted shipments and soft-deleted vehicles (SRS §3.2)
    shipment = (
        Shipment.query.join(Vehicle, Shipment.vehicle_id == Vehicle.id)
        .filter(
            Shipment.bill_of_lading == clean_bol,  # Match exact BoL safely (SQLAlchemy parameterizes this)
            Shipment.is_deleted.is_(False),        # Ignore soft-deleted shipments
            Vehicle.is_deleted.is_(False),         # Ignore shipments whose vehicle was soft-deleted
        )
        .first()  # Return the matching Shipment object, or None if not found
    )

    # Return the found Shipment (or None)
    return shipment


def get_all_active_shipments():
    """Return a list of all active (non-deleted) shipments ordered by most recently updated."""
    # Query all shipments linked to active vehicles where neither record is soft-deleted
    shipments = (
        Shipment.query.join(Vehicle, Shipment.vehicle_id == Vehicle.id)
        .filter(
            Shipment.is_deleted.is_(False),  # Only show active shipments
            Vehicle.is_deleted.is_(False),   # Only show active vehicles
        )
        .order_by(Shipment.updated_at.desc(), Shipment.id.desc())  # Show newest updates at the top
        .all()  # Fetch all matching rows as a Python list
    )

    # Return the list of active Shipment objects
    return shipments


def update_shipment_status(
    bill_of_lading: str,
    new_status: str,
    new_eta=None,
    delay_reason: str | None = None,
):
    """
    F-06 Core Function (SR-1, SR-2, SR-3):
    1. Validate the Bill of Lading and make sure new_status is in VALID_STATUSES.
    2. Validate and parse new_eta (if provided).
    3. Find the active Shipment in the shared database.
    4. Update status, eta_date, delay_reason, and updated_at, then commit immediately.
    """
    # Step 1a: Check that the Bill of Lading format is valid before querying
    if not is_valid_bill_of_lading(bill_of_lading):
        raise ValueError("Please enter a valid Bill of Lading number.")

    # Variable `clean_status`: trimmed status string from the form or caller
    clean_status = (new_status or "").strip()

    # Step 1b: Make sure the chosen status is one of the 4 allowed statuses (SR-1)
    if clean_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{clean_status}'. Choose from: {', '.join(STATUS_CHOICES)}."
        )

    # Step 2: Convert `new_eta` to a Python date object (or None if left blank)
    # Variable `parsed_eta`: validated date object or None
    parsed_eta = parse_eta_date(new_eta)

    # Step 3: Look up the active shipment record in the database
    # Variable `shipment`: the matching Shipment row from shared/models.py
    shipment = find_active_shipment(bill_of_lading)

    # If no active shipment matches that BoL, raise LookupError so the route can show a clear message
    if shipment is None:
        raise LookupError(f"Shipment '{bill_of_lading.strip()}' was not found.")

    # Step 4a: Update the transit status (F-06 SR-1)
    shipment.status = clean_status

    # Step 4b: Overwrite the existing ETA date if a new date was entered (F-06 SR-2)
    if parsed_eta is not None:
        shipment.eta_date = parsed_eta

    # Step 4c: Clean and store the optional delay reason (max 255 chars to match DB column)
    # Variable `clean_reason`: trimmed delay reason text, or None if empty
    clean_reason = delay_reason.strip()[:255] if isinstance(delay_reason, str) and delay_reason.strip() else None

    # If the shipment is marked as Delayed, save the delay reason
    if clean_status == "Delayed":
        shipment.delay_reason = clean_reason
    else:
        # If the shipment is no longer Delayed (e.g., changed to Arrived), clear old delay notes
        shipment.delay_reason = None

    # Step 4d: Record the exact UTC time of this update
    shipment.updated_at = datetime.now(timezone.utc)

    # Step 4e: Commit immediately to the central database (F-06 SR-3)
    # This ensures Randre's F-01 tracking search and Ashaya's F-04 site show the update right away
    db.session.commit()

    # Return the updated Shipment object
    return shipment


def soft_delete_shipment(bill_of_lading: str):
    """
    SRS §3.2 Safety Requirement (Soft Delete):
    Hides a shipment from active views by setting `is_deleted = True` and
    recording `deleted_at`, without permanently erasing the row from the database.
    """
    # Find the active shipment by its Bill of Lading number
    # Variable `shipment`: the active Shipment row to soft-delete
    shipment = find_active_shipment(bill_of_lading)

    # If no active shipment was found, raise LookupError
    if shipment is None:
        raise LookupError(f"Shipment '{(bill_of_lading or '').strip()}' was not found.")

    # Mark the shipment as deleted instead of calling db.session.delete()
    shipment.is_deleted = True

    # Save the UTC timestamp of when it was soft-deleted
    shipment.deleted_at = datetime.now(timezone.utc)

    # Update the updated_at timestamp as well
    shipment.updated_at = datetime.now(timezone.utc)

    # Commit the soft-delete flag to the shared database
    db.session.commit()

    # Return the soft-deleted Shipment object
    return shipment


def authenticate_staff(username: str, password: str):
    """
    SRS §3.2 Security Requirement (Staff Authentication):
    Verify a staff member's username and password against the shared `users` table.
    Returns the matching active User object if valid, or None if login fails.
    """
    # Variable `clean_username`: trimmed username text from the login form
    clean_username = (username or "").strip()

    # If either username or password is empty, authentication fails right away
    if not clean_username or not password:
        return None

    # Look up the user in the shared `users` table (only active accounts can log in)
    # Variable `user`: the matching User row from shared/models.py, or None
    user = User.query.filter_by(username=clean_username, is_active=True).first()

    # If no active user exists with that username, return None
    if user is None:
        return None

    # Safely compare the typed password against the stored password_hash using Werkzeug
    if not check_password_hash(user.password_hash, password):
        return None

    # Both username and password matched — return the authenticated User object
    return user
