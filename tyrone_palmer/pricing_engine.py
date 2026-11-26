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

    # Find the duty tier matching vehicle category and engine CC.
    duty_tiers = DutyTier.query.filter(
        DutyTier.vehicle_category == vehicle.category,
        DutyTier.min_cc <= vehicle.engine_cc,
        or_(
            DutyTier.max_cc.is_(None),
            DutyTier.max_cc >= vehicle.engine_cc
        )
    ).all()

    if not duty_tiers:
        raise ValueError("No matching duty tier found.")

    if len(duty_tiers) > 1:
        raise ValueError("Overlapping duty tiers found.")

    duty_percentage = Decimal(
        str(duty_tiers[0].duty_percentage)
    )

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
