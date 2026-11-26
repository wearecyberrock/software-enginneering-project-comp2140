# Randre Fearon — Feature Ownership (`randre_fearon/`)

- **Student ID:** `620167746`
- **Email:** `randre.fearon@mymona.uwi.edu`
- **Branch:** `member/randre`
- **Push Rule:** Only edit and push files inside `randre_fearon/`.

---

## Assigned SRS Features

### F-01: Shipment and Inventory Tracking (`Track Shipment Status`)
- **Priority:** High | **Depends on:** F-06
- **SR-1:** Query internal database using the provided Bill of Lading (BoL) number.
- **SR-2:** Retrieve and display the saved transit status and ETA of the vehicle.
- **SR-3:** Flag/visibly highlight a status when it is marked as `Delayed`.
- **Performance (SRS §3.1):** Retrieve shipment tracking data in **under 3 seconds**.
- **Test Scenarios:**
  - `TS-1 [AC-1]`: Entering an existing BoL retrieves stored status and ETA.
  - `TS-2 [AC-1]`: Error handling when an invalid or non-existent BoL is entered.
  - `TS-3 [AC-2]`: Visibly highlights status text when DB returns `Delayed` (use `.badge-delayed` from `resources/design/theme.css`).
  - `TS-4 [AC-2]`: An on-time (`In Transit`) shipment is shown without the delayed highlight.

### F-02: Manual Data Entry (`Log Vehicle Inventory`)
- **Priority:** High | **Depends on:** None
- **SR-1:** Provide a data entry form for vehicle specs, photos, BoL, and purchase details.
- **SR-2:** Require confirmation that a **deposit is paid** before a unit is activated/saved.
- **SR-3:** Save the logged unit to the central database (`shared.models.Vehicle` & `Shipment`).
- **Test Scenarios:**
  - `TS-1 [AC-1]`: Submitting all required vehicle details (with photos and deposit paid) saves the record correctly (TC-02.01).
  - `TS-2 [AC-1]`: Missing required fields are rejected and highlighted; nothing is saved (TC-02.02).
  - `TS-3 [AC-2]`: With "Deposit Paid" checked the vehicle is activated and trackable (TC-02.03).
  - `TS-4 [AC-2]`: With "Deposit Paid" unchecked, saving is blocked with "Deposit confirmation required" (TC-02.04).

---

## Files in This Folder
- `routes.py` — Flask Blueprint (`randre_bp`) for `/tracking/*` and `/inventory/*` (including `/inventory/photos/<file>` for uploaded photos)
- `tracking_service.py` — F-01 database lookup, delayed flag logic, and the view data for the results card
- `entry_service.py` — F-02 deposit validation, field validation, and saving the Vehicle + Shipment together
- `photo_upload.py` — F-02 photo checks (real image type, size, count) and safe storage
- `templates/track_shipment.html` & `templates/log_vehicle.html`
- `static/tracking.css` & `static/entry_form.js`
- `tests/test_f01_tracking.py`, `tests/test_f02_data_entry.py`, `tests/test_local_runner.py`, `tests/conftest.py`
- `run_local.py` — runs only these two features on their own (see below)

## Run the tests
```bash
pytest randre_fearon/tests/ -v
```
The tests build their own small app with only this Blueprint, so they do not depend on the other members' folders.

## Try the pages in a browser
```bash
python -m randre_fearon.run_local
```
Open `http://127.0.0.1:5000/tracking/` (F-01) and `http://127.0.0.1:5000/inventory/add` (F-02).
The first run loads the team's sample data, e.g. Bill of Lading `KJ-BOL-2026-002` is a delayed shipment.
After fusion, `python app.py` serves the same pages.

## Notes for fusion day
- Add the login rules from `shared/auth.py` (the owner is always allowed in):
  - `track_shipment()` -> `@role_required("purchasing_manager", "internal_staff")`
  - `add_vehicle()` -> `@role_required("purchasing_manager")` (SRS UC-01: only the purchasing manager logs vehicles)
  - **not** `vehicle_photo()`, because photos are also shown on the public site (F-04).
- Other members already depend on this folder: `shakir_russell/tests` call `find_shipment_by_bol()` (it must keep returning a `Shipment` or `None`) and the `/tracking/?bol=...` page.
- Uploaded photos are saved in `uploads/` (ignored by Git). Vercel's disk is temporary, so production needs cloud storage for photos.
