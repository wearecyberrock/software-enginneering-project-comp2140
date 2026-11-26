# Shakir Russell — Feature Ownership (`shakir_russell/`)

- **Student ID:** `620181663`
- **Email:** `shakir.russell@mymona.uwi.edu`
- **Branch:** `member/shakir`
- **Push Rule:** Only edit and push files inside `shakir_russell/` during feature sprint.

---

## Introduction

This folder implements **Feature F-06 (Shipment Status and ETA Updating)** and **Staff Portal Authentication (SRS §3.2)** for the Karmanjahni Shipment and Inventory Tracking System (COMP2140).

Every file in this folder is written in straightforward, beginner-friendly Flask/Python/HTML/CSS/JS with comments explaining each library, variable, line of code, and what it pulls from the shared/group codebase.

---

## Assigned SRS Feature

### F-06: Shipment Status and ETA Updating (`Update Shipment Status`)
- **Priority:** High | **Depends on:** F-02 Manual Data Entry
- **User Requirement:** Allow authorized staff to modify the transit status and estimated arrival date (ETA) of an existing shipment record when notified by suppliers.
- **SR-1:** Provide an interface (dropdown) to change a vehicle's transit status (`In Transit`, `Delayed`, `Arrived`, `Cleared`).
- **SR-2:** Allow authorized staff to override the existing ETA with a new date (and optional delay reason).
- **SR-3:** Commit updates immediately to the central database so they reflect instantly on Bill of Lading tracking queries (F-01) and customer timelines (F-04).
- **Security & Safety (SRS §3.2):**
  - Require staff authentication (`/staff/login`) and Role-Based Access Control (`owner`, `purchasing_manager`, `internal_staff`) before granting access to administrative update functions.
  - Validate Bill of Lading numbers with `shared/validators.py` to protect against SQL injection.
  - Support soft-delete (`is_deleted = True`, `deleted_at`) so outdated records are hidden without permanently erasing history.
- **Test Scenarios (Matches Test Plan `TC-06.01` & `TC-06.02`):**
  - `TS-1 [AC-1] / TC-06.01`: Authorized staff changes shipment `BOL-000` status from `In Transit` to `Arrived` and commits to DB.
  - `TS-2 [AC-2] / TC-06.02`: Entering a new ETA (`2026-12-15`) overwrites the old date (`2026-11-23`) and immediately appears on Randre's F-01 BoL tracking searches (`/tracking/?bol=BOL-000`).

---

## Files in This Folder

- `__init__.py` — Creates the `shakir_bp` Flask Blueprint registered by `app.py`.
- `status_update_service.py` — Business logic for looking up active shipments, updating status/ETA/delay reason, soft-deleting shipments, and verifying staff login passwords.
- `routes.py` — Flask routes for `/shipments/manage`, `/shipments/update/<bol>`, `/shipments/delete/<bol>`, `/staff/login`, and `/staff/logout`.
- `templates/update_shipment.html` — Staff UI extending `shared/templates/base_staff.html` for BoL lookup, status dropdown, ETA date picker, soft-delete, and active shipments table.
- `templates/staff_login.html` — Staff login UI extending `shared/templates/base_public.html`.
- `static/shipment_admin.css` — Custom layout styles built on shared design tokens from `resources/design/theme.css`.
- `static/eta_editor.js` — Plain JavaScript for toggling the Delay Reason field when `Delayed` is chosen, validating ETA dates, and confirming soft-deletes.
- `tests/conftest.py` — Isolated in-memory pytest setup with sample `BOL-000` shipment and staff accounts.
- `tests/test_f06_status_update.py` — Automated unit & acceptance tests for `TC-06.01`, `TC-06.02`, validation, SQLi safety, soft-delete, and RBAC.

---

## What This Module Pulls From Shared / Group Code

| Shared / Group File | What Shakir's Module Uses | Why |
| :--- | :--- | :--- |
| `shared/database.py` | `db` | Commits updates directly to the team's central SQLAlchemy database |
| `shared/models.py` | `Shipment`, `Vehicle`, `User` | Reads/updates the agreed database tables |
| `shared/auth.py` | `role_required` | Enforces staff login and RBAC (`owner`, `purchasing_manager`, `internal_staff`) |
| `shared/validators.py` | `is_valid_bill_of_lading` | Blocks malformed or SQL-injection BoL strings before querying |
| `shared/templates/base_staff.html` | Base staff layout | Gives `/shipments/manage` the shared Staff Portal navbar and footer |
| `shared/templates/base_public.html` | Base public layout | Gives `/staff/login` the shared public navbar and footer |
| `resources/design/theme.css` | `--kj-*` tokens & `.kj-*` classes | Matches the official Karmanjahni Navy/Gold/Cream design system |
| `randre_fearon/tracking_service.py` | `find_shipment_by_bol` (in tests) | Verifies F-06 ETA updates show up immediately in Randre's F-01 tracking |
| `ashaya_watts` | `ashaya_bp.customer_home` | Redirects staff to the public storefront on logout (when fused in `app.py`) |

---

## How to Run Shakir's Tests

```bash
pytest shakir_russell/tests -v
```
