"""
Shared Database Models (Contract agreed by all 5 members).
Supports soft delete (SRS §3.2) and updatable FX/duty tables (SRS §3.3).
"""

from datetime import datetime, timezone
from shared.database import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Roles: owner | purchasing_manager | sales_staff | internal_staff
    role = db.Column(db.String(30), nullable=False, default="internal_staff")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    # Categories: car | truck | bus | heavy_equipment | parts
    category = db.Column(db.String(40), nullable=False, default="car")
    fuel_type = db.Column(db.String(10))
    transmission = db.Column(db.String(12))
    weight_kg = db.Column(db.Integer)
    color = db.Column(db.String(50), nullable=True)
    mileage_km = db.Column(db.Integer, nullable=True)
    engine_cc = db.Column(db.Integer, nullable=False)
    features = db.Column(db.Text, nullable=True)  # e.g. "Sunroof, Keyless Entry, Alloy Rims"
    origin_country = db.Column(db.String(50), nullable=True)
    photo_urls = db.Column(db.Text, nullable=True)  # JSON array of photo URLs

    # INTERNAL ONLY — NEVER expose in Customer Interface (F-04 SR-3)
    base_foreign_price = db.Column(db.Numeric(12, 2), nullable=False)
    base_currency = db.Column(db.String(10), nullable=False, default="USD")
    deposit_paid = db.Column(db.Boolean, nullable=False, default=False)

    # SRS §3.2 Soft Delete
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    shipment = db.relationship("Shipment", back_populates="vehicle", uselist=False)

    @classmethod
    def active_inventory(cls):
        return cls.query.filter_by(is_deleted=False, deposit_paid=True).filter(
            ~cls.shipment.has(Shipment.is_deleted.is_(True))
        )


class Shipment(db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    # INTERNAL ONLY — NEVER expose in Customer Interface (F-04 SR-3)
    bill_of_lading = db.Column(db.String(100), unique=True, nullable=False, index=True)
    # Status values: In Transit | Delayed | Arrived | Cleared
    status = db.Column(db.String(30), nullable=False, default="In Transit")
    eta_date = db.Column(db.Date, nullable=True)
    departure_date = db.Column(db.Date, nullable=True)
    delay_reason = db.Column(db.String(255), nullable=True)

    # SRS §3.2 Soft Delete
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    vehicle = db.relationship("Vehicle", back_populates="shipment")


class FxRate(db.Model):
    """Updatable foreign exchange rates to JMD (SRS F-05 & §3.3 Maintainability)."""

    __tablename__ = "fx_rates"

    currency_code = db.Column(db.String(10), primary_key=True)  # USD, JPY, SGD, THB, EUR
    rate_to_jmd = db.Column(db.Numeric(12, 4), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DutyTier(db.Model):
    """Updatable government duty percentages by engine CC & category (SRS F-05 & §3.3)."""

    __tablename__ = "fuel_duty_tiers"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(80), nullable=False)
    vehicle_category = db.Column(db.String(40), nullable=False, default="car")
    lower_bound = db.Column(db.Integer, nullable=False, default=0)
    upper_bound = db.Column(db.Integer, nullable=True)  # None = no upper bound
    diesel_rate = db.Column(db.Numeric(6, 2), nullable=False)
    petrol_rate = db.Column(db.Numeric(6, 2), nullable=False)
