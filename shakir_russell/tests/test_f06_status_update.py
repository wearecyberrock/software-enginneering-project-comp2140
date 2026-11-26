"""
==============================================================================
INTRODUCTION — shakir_russell/tests/test_f06_status_update.py
==============================================================================
Author:      Shakir Russell (Student ID: 620181663)
Course:      COMP2140 — Introduction to Software Engineering
Feature:     Unit & Acceptance Tests for F-06 Shipment Status & ETA Updating

What this file does:
    Automatically tests every requirement in Shakir's SRS F-06 section and
    the team's Test Plan (TC-06.01 & TC-06.02):
    - TC-06.01 / TS-1 [AC-1]: Authorized staff changes `BOL-000` status from
      "In Transit" to "Arrived" and verifies it saves to the database.
    - TC-06.02 / TS-2 [AC-2]: Authorized staff changes `BOL-000` ETA from
      2026-11-23 to 2026-12-15 and verifies it immediately shows up in
      Randre's F-01 BoL tracking search (`/tracking/?bol=BOL-000`).
    - Delayed status + delay reason saving and clearing.
    - Input validation (invalid status, invalid date, SQL injection attempt).
    - SRS §3.2 Soft Delete (hides shipment without erasing database row).
    - SRS §3.2 Staff Authentication & Role-Based Access Control (RBAC).

Libraries used:
    - datetime (date): Python built-in for comparing saved ETA dates.

What this file pulls from the shared/group code:
    - `shared/models.py` -> `Shipment`: Checks the database directly after updates.
    - `randre_fearon/tracking_service.py` -> `find_shipment_by_bol`: Verifies
      that F-06 updates immediately reflect on Randre's F-01 tracking queries.
    - `shakir_russell/tests/conftest.py`: Automatically injects the `flask_app`,
      `client`, and `auth_client` fixtures into our test functions.
==============================================================================
"""

# Import Python's built-in date class to check saved ETA dates
from datetime import date

# Pull Randre's F-01 tracking lookup function to verify F-06 -> F-01 integration
from randre_fearon.tracking_service import find_shipment_by_bol

# Pull the shared Shipment model to inspect the database directly
from shared.models import Shipment


def test_ts1_update_status_in_transit_to_arrived(flask_app, auth_client):
    """
    TC-06.01 / TS-1 [AC-1] (SRS F-06 SR-1 & SR-3):
    Verify that authorized staff can change BOL-000 from 'In Transit' to 'Arrived'
    and that the change commits immediately to the central database.
    """
    # Step 1: Search for BOL-000 on the F-06 manage page
    # Variable `search_resp`: HTTP response from GET /shipments/manage?bol=BOL-000
    search_resp = auth_client.get("/shipments/manage?bol=BOL-000")
    assert search_resp.status_code == 200
    assert b"BOL-000" in search_resp.data
    assert b"In Transit" in search_resp.data

    # Step 2: Submit the form to change BOL-000 status from 'In Transit' to 'Arrived'
    # Variable `post_resp`: HTTP response after saving the update (following redirect)
    post_resp = auth_client.post(
        "/shipments/update/BOL-000",
        data={"status": "Arrived", "eta_date": "2026-11-23"},
        follow_redirects=True,
    )
    assert post_resp.status_code == 200
    assert b"Arrived" in post_resp.data

    # Step 3: Verify the database record itself was updated to 'Arrived'
    with flask_app.app_context():
        # Variable `saved_shipment`: the Shipment row read fresh from the database
        saved_shipment = Shipment.query.filter_by(bill_of_lading="BOL-000").first()
        assert saved_shipment is not None
        assert saved_shipment.status == "Arrived"


def test_ts2_eta_override_reflects_on_bol_search(flask_app, auth_client):
    """
    TC-06.02 / TS-2 [AC-2] (SRS F-06 SR-2 & SR-3):
    Verify that entering a new ETA (2026-12-15) overwrites the old date (2026-11-23)
    and immediately appears on Randre's F-01 Bill of Lading tracking search.
    """
    # Step 1: Submit a new ETA date (Dec 15, 2026) for BOL-000 via /shipments/manage
    # Variable `update_resp`: HTTP response from saving the new ETA
    update_resp = auth_client.post(
        "/shipments/manage",
        data={
            "bill_of_lading": "BOL-000",
            "status": "In Transit",
            "eta_date": "2026-12-15",
        },
        follow_redirects=True,
    )
    assert update_resp.status_code == 200
    assert b"2026-12-15" in update_resp.data

    # Step 2: Check via Randre's F-01 service function (`find_shipment_by_bol`)
    with flask_app.app_context():
        # Variable `tracked`: shipment returned by Randre's F-01 service
        tracked = find_shipment_by_bol("BOL-000")
        assert tracked is not None
        assert tracked.eta_date == date(2026, 12, 15)

    # Step 3: Check via Randre's F-01 web route (`/tracking/?bol=BOL-000`)
    # Variable `tracking_page`: HTML response from F-01 tracking search
    tracking_page = auth_client.get("/tracking/?bol=BOL-000")
    assert tracking_page.status_code == 200
    assert b"2026-12-15" in tracking_page.data
    assert b"2026-11-23" not in tracking_page.data


def test_delayed_status_saves_and_clears_delay_reason(flask_app, auth_client):
    """Verify setting status to 'Delayed' stores the delay reason and switching to 'Cleared' clears it."""
    # Step 1: Mark BOL-000 as Delayed with a storm reason
    resp_delayed = auth_client.post(
        "/shipments/update/BOL-000",
        data={
            "status": "Delayed",
            "eta_date": "2026-12-20",
            "delay_reason": "Tropical storm in shipping lane",
        },
        follow_redirects=True,
    )
    assert resp_delayed.status_code == 200

    # Verify Delayed status and delay reason are stored in the DB
    with flask_app.app_context():
        shipment = Shipment.query.filter_by(bill_of_lading="BOL-000").first()
        assert shipment.status == "Delayed"
        assert shipment.delay_reason == "Tropical storm in shipping lane"

    # Step 2: Update status to Cleared and confirm the old delay reason is cleared
    resp_cleared = auth_client.post(
        "/shipments/update/BOL-000",
        data={"status": "Cleared", "eta_date": "2026-12-20"},
        follow_redirects=True,
    )
    assert resp_cleared.status_code == 200

    with flask_app.app_context():
        shipment = Shipment.query.filter_by(bill_of_lading="BOL-000").first()
        assert shipment.status == "Cleared"
        assert shipment.delay_reason is None


def test_invalid_status_and_invalid_date_are_rejected(flask_app, auth_client):
    """Verify invalid status values and malformed ETA dates return HTTP 400 without changing the DB."""
    # Try submitting a status not in VALID_STATUSES
    bad_status_resp = auth_client.post(
        "/shipments/update/BOL-000",
        data={"status": "Lost At Sea", "eta_date": "2026-12-15"},
    )
    assert bad_status_resp.status_code == 400

    # Try submitting a malformed ETA date string
    bad_date_resp = auth_client.post(
        "/shipments/update/BOL-000",
        data={"status": "Arrived", "eta_date": "not-a-real-date"},
    )
    assert bad_date_resp.status_code == 400

    # Confirm BOL-000 in the database was NOT modified by either bad request
    with flask_app.app_context():
        shipment = Shipment.query.filter_by(bill_of_lading="BOL-000").first()
        assert shipment.status == "In Transit"
        assert shipment.eta_date == date(2026, 11, 23)


def test_sql_injection_bol_safely_blocked(flask_app, auth_client):
    """SRS §3.2: Verify SQL injection strings in BoL search are rejected safely."""
    # Variable `sqli_payload`: classic SQL injection test string
    sqli_payload = "'; DROP TABLE shipments; --"

    # Search using the malicious string
    resp = auth_client.get(f"/shipments/manage?bol={sqli_payload}")
    assert resp.status_code == 200
    assert b"was not found" in resp.data

    # Confirm the shipments table is still intact and BOL-000 still exists
    with flask_app.app_context():
        assert Shipment.query.filter_by(bill_of_lading="BOL-000").first() is not None


def test_soft_delete_hides_shipment_but_keeps_history(flask_app, auth_client):
    """SRS §3.2 Safety: Verify soft-deleting sets is_deleted=True without erasing the DB row."""
    # Archive (soft-delete) BOL-000 via POST /shipments/delete/BOL-000
    resp = auth_client.post("/shipments/delete/BOL-000", follow_redirects=True)
    assert resp.status_code == 200
    assert b"archived (soft-deleted)" in resp.data

    with flask_app.app_context():
        # The row must STILL exist in the database table with is_deleted=True and a deleted_at timestamp
        raw_row = Shipment.query.filter_by(bill_of_lading="BOL-000").first()
        assert raw_row is not None
        assert raw_row.is_deleted is True
        assert raw_row.deleted_at is not None

        # Randre's F-01 active tracking lookup must now hide the soft-deleted shipment
        assert find_shipment_by_bol("BOL-000") is None


def test_staff_authentication_and_rbac_enforcement(client):
    """SRS §3.2 Security: Verify login, logout, unauthenticated redirect, and role restriction."""
    # 1. Unauthenticated user visiting /shipments/manage must be redirected to /staff/login
    anon_resp = client.get("/shipments/manage", follow_redirects=False)
    assert anon_resp.status_code == 302
    assert "/staff/login" in anon_resp.headers["Location"]

    # 2. Wrong password returns HTTP 401 Unauthorized
    bad_login = client.post(
        "/staff/login",
        data={"username": "purchasing_mgr", "password": "wrongpassword"},
    )
    assert bad_login.status_code == 401
    assert b"Invalid username or password" in bad_login.data

    # 3. Logging in as sales_staff succeeds, but visiting /shipments/manage returns 403 Forbidden
    sales_login = client.post(
        "/staff/login",
        data={"username": "sales_rep", "password": "sales123"},
        follow_redirects=False,
    )
    assert sales_login.status_code == 302
    forbidden_resp = client.get("/shipments/manage")
    assert forbidden_resp.status_code == 403

    # 4. Logging out clears the session so /shipments/manage redirects back to /staff/login
    logout_resp = client.post("/staff/logout", follow_redirects=False)
    assert logout_resp.status_code == 302
    after_logout = client.get("/shipments/manage", follow_redirects=False)
    assert after_logout.status_code == 302
    assert "/staff/login" in after_logout.headers["Location"]
