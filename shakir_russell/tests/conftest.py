"""
==============================================================================
INTRODUCTION — shakir_russell/tests/conftest.py
==============================================================================
Author:      Shakir Russell (Student ID: 620181663)
Course:      COMP2140 — Introduction to Software Engineering
Feature:     Shared pytest fixtures for F-06 Shipment Status & ETA Updating

What this file does:
    Pytest automatically loads `conftest.py` before running our tests.
    Here we build a small, fresh Flask test application with an in-memory
    SQLite database (`sqlite:///:memory:`) for every test so:
    1. Tests never touch the real `karmanjahni.db` file.
    2. Each test starts with clean sample data (`BOL-000` + staff accounts).
    3. We register ONLY `shakir_bp` (F-06) and `randre_bp` (F-01 tracking)
       instead of importing `app.py`, so our tests keep passing even while
       other teammates are still finishing their branches.

Libraries used:
    - sys & pathlib (Path): Python built-ins used to add the repo root to
      Python's import path so `pytest shakir_russell/tests` works anywhere.
    - datetime (date): Python built-in for creating sample ETA dates.
    - decimal (Decimal): Python built-in for exact currency numbers in models.
    - pytest: Testing framework that provides `@pytest.fixture()`.
    - flask (Flask): Used to create our temporary test web application.
    - werkzeug.security (generate_password_hash): Creates hashed passwords for
      our test staff accounts in the `users` table.

What this file pulls from the shared/group code:
    - `shared/config.py` -> `TestConfig`: Shared test config (in-memory DB).
    - `shared/database.py` -> `db`: Shared SQLAlchemy database object.
    - `shared/models.py` -> `User`, `Vehicle`, `Shipment`: Shared DB tables.
    - `shakir_russell` -> `shakir_bp`: Shakir's Blueprint (F-06 + Staff Login).
    - `randre_fearon` -> `randre_bp`: Randre's Blueprint (F-01 BoL Tracking),
      included so we can verify F-06 TS-2 (ETA updates show up in F-01!).
==============================================================================
"""

# Import Python standard libraries for paths, dates, and exact decimal prices
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Import pytest for defining reusable test fixtures
import pytest

# Import Flask to build a lightweight test application
from flask import Flask

# Import generate_password_hash to hash test staff passwords safely (SRS §3.2)
from werkzeug.security import generate_password_hash

# Variable `ROOT`: absolute path to the top-level repository folder
ROOT = Path(__file__).resolve().parents[2]

# Add the repo root to sys.path so imports like `from shared.models import ...` always work
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def flask_app():
    """Create a fresh Flask app and in-memory database seeded with sample F-06 data."""
    # Pull Randre's F-01 Blueprint so we can test cross-feature F-06 -> F-01 tracking
    from randre_fearon import randre_bp

    # Pull Shakir's F-06 Blueprint (the code we are testing)
    from shakir_russell import shakir_bp

    # Pull shared test config, database instance, and table models from shared/
    from shared.config import TestConfig
    from shared.database import db
    from shared.models import Shipment, User, Vehicle

    # Variable `application`: temporary Flask app pointing to shared/templates/
    application = Flask(__name__, template_folder=str(ROOT / "shared" / "templates"))

    # Apply TestConfig (sets TESTING=True and SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    application.config.from_object(TestConfig)

    # Connect SQLAlchemy to this test Flask app
    db.init_app(application)

    # Register Shakir's F-06 routes and Randre's F-01 tracking routes
    application.register_blueprint(shakir_bp)
    application.register_blueprint(randre_bp)

    # Create all database tables and insert sample test data inside an app context
    with application.app_context():
        db.create_all()

        # Variable `manager`: sample authorized Purchasing Manager account
        manager = User(
            username="purchasing_mgr",
            email="purchasing@karmanjahni.com",
            password_hash=generate_password_hash("secret123"),
            role="purchasing_manager",
            is_active=True,
        )

        # Variable `sales_user`: sample Sales Staff account (used to test RBAC 403 block)
        sales_user = User(
            username="sales_rep",
            email="sales@karmanjahni.com",
            password_hash=generate_password_hash("sales123"),
            role="sales_staff",
            is_active=True,
        )

        # Variable `vehicle`: sample vehicle matching the Test Plan (TC-06.01 & TC-06.02)
        vehicle = Vehicle(
            make="Toyota",
            model="Tacoma Pickup",
            year=2021,
            category="truck",
            color="Wine Red",
            mileage_km=42000,
            engine_cc=2700,
            features="Sunroof, Keyless Entry, 4WD",
            origin_country="United States",
            base_foreign_price=Decimal("22500.00"),
            base_currency="USD",
            deposit_paid=True,
            is_deleted=False,
        )

        # Add users and vehicle first so SQLAlchemy assigns `vehicle.id`
        db.session.add_all([manager, sales_user, vehicle])
        db.session.flush()

        # Variable `shipment`: sample shipment `BOL-000` matching Test Plan TC-06.01 & TC-06.02
        shipment = Shipment(
            vehicle_id=vehicle.id,
            bill_of_lading="BOL-000",
            status="In Transit",
            eta_date=date(2026, 11, 23),
            departure_date=date(2026, 10, 20),
            delay_reason=None,
            is_deleted=False,
        )

        # Save the sample shipment into the in-memory database
        db.session.add(shipment)
        db.session.commit()

    # Hand the ready test app over to the test function
    yield application

    # Clean up the database after each test finishes
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(flask_app):
    """Return a Flask test client for sending fake GET/POST HTTP requests."""
    return flask_app.test_client()


@pytest.fixture()
def auth_client(client):
    """Return a test client that is already signed in as an authorized Purchasing Manager."""
    # Log in via POST /staff/login just like a real user in the browser
    client.post(
        "/staff/login",
        data={"username": "purchasing_mgr", "password": "secret123"},
        follow_redirects=False,
    )
    # Return the logged-in test client
    return client
