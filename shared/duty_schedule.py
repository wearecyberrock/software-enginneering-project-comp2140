"""Initial rates for the project's petrol/diesel schedule and additive schema upgrade."""
from sqlalchemy import inspect, select, text

from shared.database import db
from shared.models import DutyTier

# Category, label, inclusive lower/upper limits, petrol %, diesel %.
BRACKETS = (
    ("car", "Up to 1,000 cc", 1, 1000, 52, 39),
    ("car", "1,001–2,000 cc", 1001, 2000, 66, 52),
    ("car", "2,001–2,200 cc", 2001, 2200, 80, 52),
    ("car", "2,201 cc and above", 2201, None, 80, 66),
    ("bus", "Standard bus, any seating capacity", 0, None, 59, 46),
    ("pickup", "Under 1,850 kg unladen", 1, 1849, 39, 39),
    ("pickup", "1,851–2,200 kg unladen", 1851, 2200, 66, 52),
    ("pickup", "Over 2,200 kg unladen", 2201, None, 94, 80),
    ("truck", "Up to 2,000 kg", 1, 2000, 40, 27),
    ("truck", "Over 2,000 kg", 2001, None, 33, 27),
    ("heavy_equipment", "Special-purpose vehicle", 0, None, 33, 33),
)


def initialize_inventory():
    with db.engine.begin() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        elif conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(214005)"))
        db.metadata.create_all(conn)
        existing = {c["name"] for c in inspect(conn).get_columns("vehicles")}
        for name, kind in (("fuel_type", "VARCHAR(10)"), ("transmission", "VARCHAR(12)"),
                           ("weight_kg", "INTEGER")):
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE vehicles ADD COLUMN {name} {kind}")
        tiers = DutyTier.__table__
        ids = set(conn.execute(select(tiers.c.id)).scalars())
        for i, (category, label, low, high, petrol, diesel) in enumerate(BRACKETS, 1):
            if i not in ids:
                conn.execute(tiers.insert().values(id=i, vehicle_category=category, label=label,
                             lower_bound=low, upper_bound=high, petrol_rate=petrol, diesel_rate=diesel))


# Older inventory stored pickups and trucks together; a staff member must identify
# the actual vehicle before the new schedule can give it a reliable estimate.
import click
from flask.cli import with_appcontext
from shared.models import Shipment


@click.command("classify-vehicle")
@click.argument("bol")
@click.option("--category", type=click.Choice(["car", "pickup", "truck", "bus", "heavy_equipment"]), required=True)
@click.option("--fuel", type=click.Choice(["petrol", "diesel"]), required=True)
@click.option("--transmission", type=click.Choice(["manual", "automatic"]), required=True)
@click.option("--weight-kg", type=click.IntRange(1, 2147483647))
@with_appcontext
def classify_vehicle(bol, category, fuel, transmission, weight_kg):
    """Fill in verified specifications for an existing unit by Bill of Lading."""
    shipment = Shipment.query.filter_by(bill_of_lading=bol, is_deleted=False).one_or_none()
    if shipment is None or shipment.vehicle.is_deleted:
        raise click.ClickException("Active vehicle not found.")
    if category in ("pickup", "truck") and weight_kg is None:
        raise click.ClickException("Supply --weight-kg for this category.")
    vehicle = shipment.vehicle
    vehicle.category, vehicle.fuel_type, vehicle.transmission = category, fuel, transmission
    vehicle.weight_kg = weight_kg if category in ("pickup", "truck") else None
    db.session.commit()
    click.echo(f"Updated {bol}.")
