"""Idempotent local demonstration data for the fused application."""

from datetime import date
from secrets import token_urlsafe

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from shared.database import db
from shared.models import FxRate, Shipment, User, Vehicle


def seed_demo():
    credentials = []
    for role in ("owner", "purchasing_manager", "sales_staff", "internal_staff"):
        username = f"demo_{role}"
        if User.query.filter_by(username=username).first() is None:
            password = token_urlsafe(12)
            db.session.add(User(username=username, role=role, email=f"{username}@example.invalid",
                                password_hash=generate_password_hash(password)))
            credentials.append((username, password))

    for code, rate in {"USD": 150, "JPY": 1.05, "SGD": 115, "THB": 4.55, "EUR": 171}.items():
        if db.session.get(FxRate, code) is None:
            db.session.add(FxRate(currency_code=code, rate_to_jmd=rate))

    for bol, make, model, status, eta in (
        ("BOL-000", "Honda", "Fit", "In Transit", date(2026, 11, 23)),
        ("BOL-001", "Honda", "Civic", "Delayed", date(2026, 12, 1)),
        ("BOL-002", "Toyota", "Corolla", "Arrived", None),
    ):
        if Shipment.query.filter_by(bill_of_lading=bol).first() is None:
            vehicle = Vehicle(make=make, model=model, year=2021, engine_cc=1500,
                              fuel_type="petrol", transmission="automatic", base_foreign_price=10000, base_currency="USD", deposit_paid=True)
            vehicle.shipment = Shipment(bill_of_lading=bol, status=status, eta_date=eta)
            db.session.add(vehicle)
    db.session.commit()
    return credentials


@click.command("seed-demo")
@with_appcontext
def seed_demo_command():
    """Create classroom records and print passwords for newly created demo users."""
    credentials = seed_demo()
    for username, password in credentials:
        click.echo(f"{username}  {password}")
    click.echo("Demo data ready. Existing records and passwords are preserved.")
