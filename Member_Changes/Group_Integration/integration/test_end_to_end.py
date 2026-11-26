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
    assert landing == "/tablet/"
    for path in ("/tablet/", "/tracking/", "/inventory/add", "/shipments/manage", "/admin/pricing-rates"):
        assert public.get(path).location.endswith("/staff/login")
    assert sales.get("/inventory/add").status_code == 403

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    response = purchaser.post("/inventory/add", data={
        "make": "Toyota", "model": "Hilux", "year": "2021", "category": "truck",
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
    profile = f"/tablet/vehicle/{record['id']}"
    detail = f"/vehicle/{record['id']}"
    tablet = sales.get(profile).get_data(as_text=True)
    assert "42,500 km" in tablet and "J$3,607,500.00" in tablet
    assert len(set(record["photo_urls"])) == 2
    for url in record["photo_urls"]:
        assert url in tablet and url in public.get(detail).get_data(as_text=True)
        assert public.get(url).data == png
    assert record["estimated_jmd_price"] == "3607500.00"

    purchaser.get("/admin/pricing-rates")
    with purchaser.session_transaction() as staff:
        token = staff["pricing_csrf_token"]
    result = purchaser.post("/admin/pricing-rates", data={"csrf_token": token, "action": "update_fx",
                            "currency_code": "USD", "rate_to_jmd": "160"}, follow_redirects=True)
    assert result.status_code == 200
    assert public_record()["estimated_jmd_price"] == "3848000.00"
    assert "J$3,848,000.00" in sales.get(profile).get_data(as_text=True)
    assert b"3848000.00" in public.get(detail).data

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
    assert {"bill_of_lading", "base_foreign_price", "base_currency", "deposit_paid"}.isdisjoint(record)
    assert b"BOL-205" not in public.get(detail).data
    assert purchaser.post("/shipments/delete/BOL-205").status_code == 302
    assert public_record()["estimated_arrival"] is None
    assert public_record()["availability"] == "Availability pending"
    assert b"Shipment not found" in purchaser.get("/tracking/?bol=BOL-205").data
