"""F-05 Pricing Engine: Dynamic JMD estimate using active FX rates and CC duty tiers."""

from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import or_
from shared.models import Vehicle, FxRate, DutyTier


def calculate_estimated_jmd_price(vehicle: Vehicle) -> Decimal:
    """Calculate the estimated vehicle price in Jamaican dollars."""

    # SR-1: Retrieve stored vehicle pricing information.
    base_price = Decimal(str(vehicle.base_foreign_price))

    if base_price < 0:
        raise ValueError("Vehicle base price cannot be negative.")

    if vehicle.engine_cc < 0:
        raise ValueError("Engine CC cannot be negative.")

    # SR-2: Retrieve the current foreign exchange rate.
    fx_rate = FxRate.query.filter_by(
        currency_code=vehicle.base_currency
    ).first()

    if fx_rate is None:
        raise ValueError("Exchange rate not found.")

    rate = Decimal(str(fx_rate.rate_to_jmd))

    if rate <= 0:
        raise ValueError("Exchange rate must be positive.")

    if vehicle.fuel_type not in ("petrol", "diesel"):
        raise ValueError("Fuel type is needed for a duty estimate.")
    if vehicle.category == "car":
        size = vehicle.engine_cc
    elif vehicle.category in ("truck", "pickup"):
        size = vehicle.weight_kg
        if not size:
            raise ValueError("Vehicle weight is needed for a duty estimate.")
    else:
        size = 0
    tiers = DutyTier.query.filter(
        DutyTier.vehicle_category == vehicle.category, DutyTier.lower_bound <= size,
        or_(DutyTier.upper_bound.is_(None), DutyTier.upper_bound >= size),
    ).all()
    if len(tiers) != 1:
        raise ValueError("No unique duty bracket for this vehicle.")
    duty_percentage = tiers[0].petrol_rate if vehicle.fuel_type == "petrol" else tiers[0].diesel_rate
    if duty_percentage < 0:
        raise ValueError("Duty percentage cannot be negative.")

    # Convert the foreign price to Jamaican dollars.
    base_jmd = base_price * rate

    # Apply the government duty percentage.
    estimated_total = base_jmd * (
        Decimal("1") + duty_percentage / Decimal("100")
    )

    # SR-3: Return the estimated JMD price to two decimal places.
    return estimated_total.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
