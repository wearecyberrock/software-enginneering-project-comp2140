"""Exercise all five blueprints against one database via the real Flask routes."""

import base64
from io import BytesIO

from app import create_app
from shared.config import TestConfig
from shared.demo_data import seed_demo


def test_full_karmanjahni_lifecycle(tmp_path):
    app = create_app(TestConfig)
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    with app.app_context():
        passwords = dict(seed_demo())
        assert seed_demo() == []

    def sign_in(role):
        client = app.test_client()
        username = f"demo_{role}"
        response = client.post("/staff/login", data={"username": username,
                               "password": passwords[username]}, follow_redirects=True)
        assert response.status_code == 200
        return client, response.request.path

    purchaser, _ = sign_in("purchasing_manager")
    sales, landing = sign_in("sales_staff")
    public = app.test_client()
    assert landing == "/browse"
    for path in ("/tablet/", "/tracking/", "/inventory/add", "/shipments/manage", "/admin/pricing-rates"):
        assert public.get(path).location.endswith("/staff/login")
    assert sales.get("/inventory/add").status_code == 403

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    response = purchaser.post("/inventory/add", data={
        "make": "Toyota", "model": "Hilux", "year": "2021", "category": "pickup", "fuel_type": "diesel", "transmission": "automatic", "weight_kg": "2000",
        "engine_cc": "2800", "mileage_km": "42500", "base_foreign_price": "18500",
        "base_currency": "USD", "bill_of_lading": "BOL-205", "deposit_paid": "on",
        "photos": [(BytesIO(png), "front.png"), (BytesIO(png), "side.png")],
    }, follow_redirects=True)
    assert response.status_code == 200 and b"BOL-205" in response.data

    def public_record():
        rows = public.get("/api/public/vehicles?q=Toyota+Hilux").get_json()
        assert len(rows) == 1
        return rows[0]

    record = public_record()
    assert record["transmission"] == "automatic" and record["fuel_type"] == "diesel"
    assert public.get("/api/public/vehicles?q=Hilux&transmission=manual").get_json() == []
    assert public.get("/api/public/vehicles?q=Hilux&transmission=automatic").get_json() == [record]
    profile = f"/tablet/vehicle/{record['id']}"
    detail = f"/vehicle/{record['id']}"
    tablet = sales.get(profile).get_data(as_text=True)
    assert "42,500 km" in tablet and "J$4,218,000.00" in tablet
    assert len(set(record["photo_urls"])) == 2
    for url in record["photo_urls"]:
        assert url in tablet and url in public.get(detail).get_data(as_text=True)
        assert public.get(url).data == png
    assert record["estimated_jmd_price"] == "4218000.00"

    purchaser.get("/admin/pricing-rates")
    with purchaser.session_transaction() as staff:
        token = staff["pricing_csrf_token"]
    result = purchaser.post("/admin/pricing-rates", data={"csrf_token": token, "action": "update_fx",
                            "currency_code": "USD", "rate_to_jmd": "160"}, follow_redirects=True)
    assert result.status_code == 200
    assert public_record()["estimated_jmd_price"] == "4499200.00"
    assert "J$4,499,200.00" in sales.get(profile).get_data(as_text=True)
    assert b"4,499,200.00" in public.get(detail).data
    assert b"Hilux" in public.get("/upcoming-arrivals").data
    assert b"Hilux" not in public.get("/browse").data
    assert b"Staff Login" not in purchaser.get("/").data
    assert b"Staff Login" in public.get("/").data

    for status in ("Delayed", "Cleared"):
        result = purchaser.post("/shipments/manage", data={"bill_of_lading": "BOL-205",
                                "status": status, "eta_date": "2026-12-15"}, follow_redirects=True)
        assert result.status_code == 200
        tracking = purchaser.get("/tracking/?bol=BOL-205").get_data(as_text=True)
        assert status in tracking and "2026-12-15" in tracking
        if status == "Delayed":
            assert "badge-delayed" in tracking
            assert public_record()["estimated_arrival"] == "2026-12-15"
            assert b"2026-12-15" in public.get(detail).data
    assert public_record()["availability"] == "Available Now"
    assert b"J$4,499,200.00" in public.get("/browse").data
    assert b"Hilux" not in public.get("/upcoming-arrivals").data
    for section, expected in (("available", 1), ("upcoming", 0)):
        assert len(public.get("/api/public/vehicles", query_string={"q": "Hilux", "section": section}).get_json()) == expected
    assert {"bill_of_lading", "base_foreign_price", "base_currency", "deposit_paid"}.isdisjoint(record)
    assert b"BOL-205" not in public.get(detail).data
    assert purchaser.post("/shipments/delete/BOL-205").status_code == 302
    assert public.get("/api/public/vehicles?q=Hilux").get_json() == []
    assert public.get(detail).status_code == 404
    assert sales.get(profile).status_code == 404
    assert public.get(f"/pricing/estimate/{record['id']}").status_code == 404
    assert b"Shipment not found" in purchaser.get("/tracking/?bol=BOL-205").data
    assert sales.post("/shipments/BOL-205/restore").status_code == 403
    assert purchaser.post("/shipments/BOL-205/vehicle", data={}).status_code == 404
    result = purchaser.post("/shipments/BOL-205/restore", follow_redirects=True)
    assert result.status_code == 200 and b"returned to inventory" in result.data
    assert public_record()["availability"] == "Available Now"
    assert public_record()["photo_urls"] == record["photo_urls"]

    specifications = dict(make="Toyota", model="Hilux", category="pickup", fuel_type="petrol",
                          transmission="manual", weight_kg="2000", year="2021", engine_cc="2800",
                          color="White", mileage_km="45000", features="4WD", origin_country="Japan")
    path = "/shipments/BOL-205/vehicle"
    assert sales.post(path, data=specifications).status_code == 403
    bad = purchaser.post(path, data=dict(specifications, weight_kg=""))
    assert bad.status_code == 400 and b"whole, positive kilograms" in bad.data
    assert public_record()["fuel_type"] == "diesel"
    good = purchaser.post(path, data=specifications, follow_redirects=True)
    assert good.status_code == 200 and b"Vehicle specifications updated" in good.data
    updated = public_record()
    assert updated["fuel_type"] == "petrol" and updated["transmission"] == "manual"
    assert updated["estimated_jmd_price"] == "4913600.00"
    assert updated["photo_urls"] == record["photo_urls"]
