"""F-05 Service: Manage updatable FX rates and CC duty percentages in DB (SRS §3.3)."""

from decimal import Decimal, InvalidOperation
from shared.database import db
from shared.models import FxRate, DutyTier


def get_all_fx_rates():
    return FxRate.query.order_by(FxRate.currency_code).all()


def get_all_duty_tiers():
    return DutyTier.query.order_by(DutyTier.id).all()


def _rate_value(raw, minimum, maximum, places):

    try:
        value = Decimal(str(raw))
        if (not value.is_finite() or not minimum <= value <= maximum
                or value != value.quantize(Decimal(1).scaleb(-places))):
            raise ValueError
    except (ValueError, InvalidOperation):
        raise ValueError(f"Enter a value from {minimum} to {maximum} with at most {places} decimal places.") from None
    return value


def update_fx_rate(currency_code, new_rate):
    rate = db.session.get(FxRate, currency_code)
    if rate is None:
        raise ValueError("Unknown currency.")
    rate.rate_to_jmd = _rate_value(new_rate, Decimal("0.0001"), Decimal("99999999.9999"), 4)
    db.session.commit()


def update_duty_tier(tier_id, petrol, diesel):
    tier = db.session.get(DutyTier, tier_id)
    if tier is None:
        raise ValueError("Unknown duty tier.")
    petrol_rate = _rate_value(petrol, 0, Decimal("9999.99"), 2)
    diesel_rate = _rate_value(diesel, 0, Decimal("9999.99"), 2)
    tier.petrol_rate, tier.diesel_rate = petrol_rate, diesel_rate
    db.session.commit()
