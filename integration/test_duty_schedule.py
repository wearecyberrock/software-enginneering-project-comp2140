from decimal import Decimal
import pytest
from app import create_app
from shared.config import TestConfig
from shared.models import FxRate, Vehicle
from shared.database import db
from tyrone_palmer.pricing_engine import calculate_estimated_jmd_price


@pytest.mark.parametrize("category,size,petrol,diesel", [
    ("car",1000,52,39), ("car",1001,66,52), ("car",2000,66,52),
    ("car",2001,80,52), ("car",2200,80,52), ("car",2201,80,66),
    ("bus",3000,59,46), ("pickup",1849,39,39), ("pickup",1851,66,52),
    ("pickup",2200,66,52), ("pickup",2201,94,80), ("truck",2000,40,27),
    ("truck",2001,33,27), ("heavy_equipment",4000,33,33),
    ("pickup",1850,None,None), ("parts",100,None,None),
])
def test_project_duty_matrix(category,size,petrol,diesel):
    app = create_app(TestConfig)
    with app.app_context():
        db.session.add(FxRate(currency_code="USD",rate_to_jmd=1))
        db.session.commit()
        for fuel,percentage in (("petrol",petrol),("diesel",diesel)):
            unit = Vehicle(category=category, engine_cc=size if category=="car" else 2800,
                           weight_kg=size, fuel_type=fuel, base_currency="USD",base_foreign_price=100)
            if percentage is None:
                with pytest.raises(ValueError):
                    calculate_estimated_jmd_price(unit)
            else:
                assert calculate_estimated_jmd_price(unit) == Decimal(100 + percentage)
