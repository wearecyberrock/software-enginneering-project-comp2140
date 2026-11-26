"""Unit & Acceptance Tests for F-02 Manual Data Entry (Randre Fearon).

How these tests line up with the Test Plan (TS = test scenario, TC = test case):
    TS-1 [AC-1]  TC-02.01  all details + photos + deposit paid  -> vehicle saved and active
    TS-2 [AC-1]  TC-02.02  required fields missing              -> rejected, fields highlighted
    TS-3 [AC-2]  TC-02.03  "Deposit Paid" checked               -> vehicle activated and trackable
    TS-4 [AC-2]  TC-02.04  "Deposit Paid" unchecked             -> blocked with a deposit warning
The rest are extra checks for validation, photos and security (SRS 3.2).

Run with:  pytest randre_fearon/tests/test_f02_data_entry.py -v
"""

import base64
import json
import os
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest

from randre_fearon.entry_service import EntryValidationError, log_new_vehicle
from shared.database import db
from shared.models import Shipment, Vehicle

# A real 1x1 pixel PNG, so the "is this really an image?" check has something genuine to read.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def valid_form(**overrides):
    """The Hilux from the Test Plan (TC-02.01). Pass a value of None to leave a field out."""
    form = dict(
        make="Toyota", model="Hilux", year="2021", category="pickup", engine_cc="2800", fuel_type="diesel", transmission="automatic", weight_kg="2000",
        base_foreign_price="18500", base_currency="USD", bill_of_lading="BOL-205",
        deposit_paid="on",
    )
    form.update(overrides)
    return form


def post_form(client, form, photos=()):
    """Send the Add Unit form the way a browser does. `photos` is a list of (bytes, filename)."""
    data = {key: value for key, value in form.items() if value is not None}
    if photos:
        data["photos"] = [(BytesIO(content), name) for content, name in photos]
    return client.post("/inventory/add", data=data, content_type="multipart/form-data")


def vehicle_count(flask_app):
    with flask_app.app_context():
        return Vehicle.query.count()


def upload_files(flask_app):
    folder = flask_app.config["UPLOAD_FOLDER"]
    return os.listdir(folder) if os.path.isdir(folder) else []


# ---------------------------------------------------------------------------
# The four test scenarios from the SRS / Test Plan
# ---------------------------------------------------------------------------

def test_ts1_valid_vehicle_saved(flask_app, client):
    """TS-1 / TC-02.01: 2021 Toyota Hilux, BOL-205, 2800 cc, $18,500, 2 photos, deposit paid."""
    response = post_form(client, valid_form(), photos=[(PNG, "front.png"), (PNG, "side.png")])

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/inventory/add?saved=BOL-205")

    with flask_app.app_context():
        vehicle = Vehicle.query.one()
        assert (vehicle.year, vehicle.make, vehicle.model) == (2021, "Toyota", "Hilux")
        assert vehicle.engine_cc == 2800
        assert vehicle.base_foreign_price == Decimal("18500.00")
        assert vehicle.deposit_paid is True and vehicle.is_deleted is False  # active, in the inventory list
        assert vehicle.shipment.bill_of_lading == "BOL-205"
        photo_urls = json.loads(vehicle.photo_urls)
        assert len(photo_urls) == 2

    # Both photos really exist on disk and can be fetched through the photo route.
    assert len(upload_files(flask_app)) == 2
    photo = client.get(photo_urls[0])
    assert photo.status_code == 200 and photo.data == PNG

    # "BOL-205 opened in tracking"
    tracking = client.get("/tracking/?bol=BOL-205").get_data(as_text=True)
    assert "2021 Toyota Hilux" in tracking and "In Transit" in tracking

    # After the redirect the form page confirms the save and links to tracking.
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert 'id="saved-banner"' in page and "Vehicle saved" in page
    assert "/tracking/?bol=BOL-205" in page


def test_ts2_form_rejects_missing_required_fields(flask_app, client):
    """TS-2 / TC-02.02: Honda Fit with blank Bill of Lading and Base Price (deposit checked)."""
    form = valid_form(make="Honda", model="Fit", year="2019", engine_cc="1500",
                      bill_of_lading="", base_foreign_price="")
    response = post_form(client, form)
    html = response.get_data(as_text=True)

    assert response.status_code == 400
    assert vehicle_count(flask_app) == 0                      # no incomplete record saved
    assert "Bill of Lading number is required" in html
    assert "Base price is required" in html
    # Both missing fields are highlighted (red border + message), and the others are left alone.
    assert 'id="bill_of_lading-error"' in html and 'id="base_foreign_price-error"' in html
    assert html.count("field-invalid") >= 2
    assert 'id="make-error"' not in html
    assert 'value="Honda"' in html                            # what was typed is kept for the user


def test_ts3_deposit_paid_checked_activates_vehicle(flask_app, client):
    """TS-3 / TC-02.03: 2019 Honda Civic, BOL-206, $13,000, 'Deposit Paid' checked."""
    form = valid_form(make="Honda", model="Civic", year="2019", category="car", engine_cc="1800",
                      bill_of_lading="BOL-206", base_foreign_price="13000")
    response = post_form(client, form)

    assert response.status_code == 302
    with flask_app.app_context():
        vehicle = Vehicle.query.one()
        assert vehicle.deposit_paid is True and vehicle.is_deleted is False
    tracking = client.get("/tracking/?bol=BOL-206").get_data(as_text=True)   # immediately trackable
    assert "2019 Honda Civic" in tracking


def test_ts4_deposit_unchecked_blocks_saving(flask_app, client):
    """TS-4 / TC-02.04: 2020 Nissan X-Trail, BOL-207, $14,000, 'Deposit Paid' left unchecked."""
    form = valid_form(make="Nissan", model="X-Trail", year="2020", category="car", engine_cc="2000",
                      bill_of_lading="BOL-207", base_foreign_price="14000", deposit_paid=None)
    response = post_form(client, form, photos=[(PNG, "front.png")])
    html = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "Deposit confirmation required" in html
    assert 'id="deposit_paid-error"' in html
    assert vehicle_count(flask_app) == 0
    assert upload_files(flask_app) == []                      # rejected form leaves no stray photo files
    assert "Please choose them again" in html                 # user is told the photos were not kept
    tracking = client.get("/tracking/?bol=BOL-207").get_data(as_text=True)
    assert "Shipment not found" in tracking                   # "BOL-207 lookup found no shipment"


# ---------------------------------------------------------------------------
# The service on its own (what the README calls log_new_vehicle)
# ---------------------------------------------------------------------------

def test_service_raises_value_error_when_deposit_not_paid(flask_app):
    with flask_app.app_context():
        with pytest.raises(ValueError, match="Deposit confirmation required"):
            log_new_vehicle(valid_form(deposit_paid=None))
        assert Vehicle.query.count() == 0


@pytest.mark.parametrize("unchecked", ["", "off", "false", "0", False, None])
def test_service_only_accepts_a_real_tick_as_deposit_paid(flask_app, unchecked):
    with flask_app.app_context():
        with pytest.raises(EntryValidationError) as excinfo:
            log_new_vehicle(valid_form(deposit_paid=unchecked))
        assert excinfo.value.errors == {"deposit_paid": "Deposit confirmation required"}


@pytest.mark.parametrize("ticked", ["on", "true", "1", True])
def test_service_saves_vehicle_and_shipment_together(flask_app, ticked):
    with flask_app.app_context():
        vehicle = log_new_vehicle(valid_form(deposit_paid=ticked))
        assert vehicle.id is not None
        assert vehicle.shipment.bill_of_lading == "BOL-205"
        assert vehicle.shipment.status == "In Transit"
        assert vehicle.photo_urls == "[]"                    # contract: always a JSON list
        assert Shipment.query.count() == 1


def test_service_collects_every_problem_at_once(flask_app):
    with flask_app.app_context():
        with pytest.raises(EntryValidationError) as excinfo:
            log_new_vehicle({"deposit_paid": ""})
        assert set(excinfo.value.errors) == {
            "make", "model", "year", "engine_cc", "base_foreign_price", "bill_of_lading", "deposit_paid", "fuel_type", "transmission",
        }


def test_money_can_be_typed_with_dollar_sign_and_commas(flask_app):
    with flask_app.app_context():
        assert log_new_vehicle(valid_form(base_foreign_price="$18,500")).base_foreign_price == Decimal("18500.00")
        assert log_new_vehicle(valid_form(bill_of_lading="BOL-2", base_foreign_price="9,999.5")
                               ).base_foreign_price == Decimal("9999.50")


def test_optional_details_are_saved_when_given_and_blank_when_not(flask_app):
    with flask_app.app_context():
        full = log_new_vehicle(valid_form(
            color="Wine Red", mileage_km="42,000", features="Sunroof, Keyless Entry",
            origin_country="United States", departure_date="2026-11-15", eta_date="2026-12-30",
        ))
        assert (full.color, full.mileage_km, full.features) == ("Wine Red", 42000, "Sunroof, Keyless Entry")
        assert full.origin_country == "United States"
        assert full.shipment.departure_date == date(2026, 11, 15)
        assert full.shipment.eta_date == date(2026, 12, 30)

        bare = log_new_vehicle(valid_form(bill_of_lading="BOL-BARE"))
        assert bare.color is None and bare.mileage_km is None and bare.features is None
        assert bare.shipment.eta_date is None


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field, value", [
    ("year", "20x1"), ("year", "1800"), ("year", "3000"),
    ("engine_cc", "0"), ("engine_cc", "abc"), ("engine_cc", "28.5"),
    ("base_foreign_price", "0"), ("base_foreign_price", "-5"), ("base_foreign_price", "abc"),
    ("base_foreign_price", "NaN"), ("base_foreign_price", "1e500"), ("base_foreign_price", "99999999999"),
    ("mileage_km", "-1"), ("mileage_km", "lots"),
    ("category", "spaceship"), ("base_currency", "XYZ"),
    ("bill_of_lading", "A"), ("bill_of_lading", "BOL 205"), ("bill_of_lading", "BOL-205'; DROP TABLE vehicles; --"),
    ("make", "x" * 81), ("departure_date", "next week"), ("eta_date", "2026-13-45"),
])
def test_bad_values_are_rejected_and_nothing_is_saved(flask_app, field, value):
    with flask_app.app_context():
        with pytest.raises(EntryValidationError) as excinfo:
            log_new_vehicle(valid_form(**{field: value}))
        assert field in excinfo.value.errors
        assert Vehicle.query.count() == 0 and Shipment.query.count() == 0


def test_arrival_date_cannot_be_before_departure(flask_app):
    with flask_app.app_context():
        with pytest.raises(EntryValidationError) as excinfo:
            log_new_vehicle(valid_form(departure_date="2026-12-01", eta_date="2026-11-01"))
        assert "eta_date" in excinfo.value.errors


def test_duplicate_bill_of_lading_is_rejected(flask_app, client):
    assert post_form(client, valid_form()).status_code == 302
    response = post_form(client, valid_form(model="Another"))
    assert response.status_code == 400
    assert "already in the system" in response.get_data(as_text=True)
    assert vehicle_count(flask_app) == 1                      # the second vehicle was not left half-saved


def test_soft_deleted_bill_of_lading_still_counts_as_used(flask_app):
    """The database column is UNIQUE across every row, deleted or not."""
    with flask_app.app_context():
        old = log_new_vehicle(valid_form())
        old.shipment.is_deleted = True
        db.session.commit()
        with pytest.raises(EntryValidationError) as excinfo:
            log_new_vehicle(valid_form(model="Again"))
        assert "bill_of_lading" in excinfo.value.errors


def test_sql_injection_text_does_not_harm_the_database(flask_app, client):
    attack = "Robert'); DROP TABLE vehicles;--"
    assert post_form(client, valid_form(make=attack)).status_code == 302   # stored as plain text
    with flask_app.app_context():
        assert Vehicle.query.one().make == attack                           # the table is still there
    assert post_form(client, valid_form(bill_of_lading="B'; DROP TABLE shipments;--")).status_code == 400
    with flask_app.app_context():
        assert Shipment.query.count() == 1


def test_form_values_are_escaped_when_the_page_reloads(flask_app, client):
    html = post_form(client, valid_form(make='"><script>alert(1)</script>', deposit_paid=None)).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

def test_vehicle_can_be_saved_without_photos(flask_app, client):
    assert post_form(client, valid_form()).status_code == 302
    with flask_app.app_context():
        assert json.loads(Vehicle.query.one().photo_urls) == []


def test_file_that_is_not_really_an_image_is_rejected(flask_app, client):
    response = post_form(client, valid_form(), photos=[(b"this is just text, not a picture", "fake.jpg")])
    assert response.status_code == 400
    assert "not a valid image" in response.get_data(as_text=True)
    assert vehicle_count(flask_app) == 0 and upload_files(flask_app) == []


def test_image_with_a_wrong_file_extension_is_rejected(flask_app, client):
    response = post_form(client, valid_form(), photos=[(PNG, "notes.txt")])
    assert response.status_code == 400 and vehicle_count(flask_app) == 0


def test_photo_over_five_megabytes_is_rejected(flask_app, client):
    big = PNG[:12] + b"0" * (5 * 1024 * 1024)
    response = post_form(client, valid_form(), photos=[(big, "huge.png")])
    assert response.status_code == 400
    assert "larger than 5 MB" in response.get_data(as_text=True)
    assert vehicle_count(flask_app) == 0


def test_more_than_ten_photos_are_rejected(flask_app, client):
    response = post_form(client, valid_form(), photos=[(PNG, f"p{n}.png") for n in range(11)])
    assert response.status_code == 400
    assert "at most 10" in response.get_data(as_text=True)
    assert upload_files(flask_app) == []


def test_uploaded_photos_get_random_names_not_the_users_file_name(flask_app, client):
    post_form(client, valid_form(), photos=[(PNG, "../../evil name.png")])
    names = upload_files(flask_app)
    assert len(names) == 1 and names[0].endswith(".png") and "evil" not in names[0]


def test_photo_route_cannot_read_files_outside_the_upload_folder(flask_app, client):
    assert client.get("/inventory/photos/missing.png").status_code == 404
    assert client.get("/inventory/photos/..%2F..%2Fapp.py").status_code == 404
    assert client.get("/inventory/photos/../../app.py").status_code == 404


# ---------------------------------------------------------------------------
# The form page itself
# ---------------------------------------------------------------------------

def test_form_page_has_every_field_and_the_deposit_checkbox(client):
    response = client.get("/inventory/add")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'enctype="multipart/form-data"' in html
    for name in ("make", "model", "year", "category", "color", "mileage_km", "engine_cc", "origin_country",
                 "features", "bill_of_lading", "base_foreign_price", "base_currency", "departure_date",
                 "eta_date", "photos", "deposit_paid"):
        assert f'name="{name}"' in html, name
    assert 'type="checkbox"' in html
    assert "/randre/static/entry_form.js" in html and "/randre/static/tracking.css" in html
    assert "Vehicle saved" not in html and "Vehicle not saved" in html and 'id="form-errors"' in html
    assert " hidden>" in html                                  # the error box starts hidden


def test_saved_banner_is_only_shown_for_a_bill_of_lading_that_exists(client):
    html = client.get("/inventory/add?saved=NOT-A-REAL-ONE").get_data(as_text=True)
    assert 'id="saved-banner"' not in html


def test_static_files_are_served(client):
    assert client.get("/randre/static/entry_form.js").status_code == 200
    assert client.get("/randre/static/tracking.css").status_code == 200
