# Karmanjahni Shipment and Inventory Tracking System

**Course:** COMP2140 – Introduction to Software Engineering (UWI Mona)  
**Group:** `THUR_9-11_G01`  
**Course Instructor:** Dr. Ricardo Anderson  
**Studio Facilitator:** Dr. Claudine Allen  
**Client:** Karmanjahni Company Limited (Kingston, Jamaica)

---

## Tech Stack

- **Backend:** Python 3.11+ with **Flask** (Modular Blueprints) & **SQLAlchemy**
- **Frontend:** HTML5, CSS3 (shared `resources/design/theme.css`), Vanilla JavaScript
- **Database:** SQLite (local development) / PostgreSQL (production deployment)
- **Testing:** `pytest`
- **Cloud Hosting:** Vercel (`vercel.json` included per SRS §3.3)

---

## Team Ownership & Folder Structure

> **GOLDEN RULE:** Every team member works and pushes **ONLY** inside their own named folder during development. Do **not** modify another member's folder. Shared database contracts live in `shared/` and brand styling lives in `resources/design/`. Once everyone finishes their feature and tests, we come together and fuse everything through `app.py` and `integration/`.

| Folder | Team Member | Student ID | SRS Feature(s) |
| :--- | :--- | :--- | :--- |
| [`randre_fearon/`](randre_fearon/README.md) | **Randre Fearon** | `620167746` | **F-01** Shipment & Inventory Tracking, **F-02** Manual Data Entry |
| [`amanda_morgan/`](amanda_morgan/README.md) | **Amanda Morgan** | `620170322` | **F-03** Mobile Portability Access (Tablet Vehicle Specs & Gallery) |
| [`ashaya_watts/`](ashaya_watts/README.md) | **Ashaya Watts** | `620169617` | **F-04** Customer Interface Search (Restricted Public Storefront) |
| [`tyrone_palmer/`](tyrone_palmer/README.md) | **Tyrone Palmer** | `620181645` | **F-05** Dynamic Pricing Estimates (FX Rates & Engine CC Duties) |
| [`shakir_russell/`](shakir_russell/README.md) | **Shakir Russell** | `620181663` | **F-06** Shipment Status & ETA Updating (Staff Admin) |

### Shared & Integration Directories

- `resources/design/` — Official Karmanjahni color palette, theme CSS, design tokens, brand guide, and logo assets.
- `shared/` — Shared SQLAlchemy models (`Vehicle`, `Shipment`, `FxRate`, `DutyTier`, `User`), RBAC helpers, validators, seed SQL, and base HTML templates.
- `docs/` — API & DB schema contract (`API_AND_DB_CONTRACT.md`) and Git workflow (`GIT_WORKFLOW.md`).
- `integration/` — Final fusion checklist and end-to-end tests.

---

## Run the integrated project on Windows

Extract the whole folder and open the directory containing `app.py` in VS Code.
From PowerShell, with Python 3.11 or 3.12 installed, run:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m flask --app app seed-demo
.\venv\Scripts\python.exe -m flask --app app run
```

Open http://127.0.0.1:5000/ for the public storefront. Choose **Staff Login**
and use the username and password printed by the setup command. Save the
passwords when they appear. Repeating setup preserves existing accounts,
rates, units and shipment updates. Demo exchange rates are illustrative.

| Account | Pages to demonstrate |
| --- | --- |
| demo_owner | All staff pages and pricing settings |
| demo_purchasing_manager | Vehicle entry, tracking, shipment updates and rates |
| demo_internal_staff | Tracking and shipment updates |
| demo_sales_staff | Mobile-friendly inventory, photos, mileage and JMD price |

Browse Inventory lists arrived and cleared vehicles. Upcoming Arrivals lists in-transit and delayed vehicles. Sales staff open vehicle details from either page on a phone or tablet. BOL-002 is an arrived Corolla in the demo.

Start with BOL-000 (In Transit) and BOL-001 (Delayed). Log the Hilux as
BOL-205 with two photos. Update its status and ETA in shipment management,
view the photos and price as a salesperson, and search for Hilux signed out.
For the updated recording, enter the USD 18,500 Hilux as a diesel pickup with
automatic transmission and 2,000 kg unladen weight (demo inputs). Its 52% rate
gives J$4,218,000 at 150 JMD/USD and J$4,499,200 at 160 JMD/USD.
The rate editor stores separate petrol and diesel percentages for each bracket.
Exactly 1,850 kg for a pickup falls between the supplied brackets, so the unit
can be saved but its estimate is unavailable. Parts also have no supplied rate.
Special-purpose heavy equipment uses the project-specified 33% rate.

If upgrading an existing project, keep the existing database and uploads. On
startup, the app adds the vehicle columns and initializes the new duty schedule;
existing accounts, vehicles, FX rates and previous rate table are retained.
New specifications for legacy vehicles stay unknown until confirmed. For example,
to classify an existing BOL-205 after verifying the details:

```powershell
.\venv\Scripts\python.exe -m flask --app app classify-vehicle BOL-205 --category pickup --fuel diesel --transmission automatic --weight-kg 2000
```

The local database persists between runs. Stop the server with Ctrl+C.

To run all tests, including the cross-member workflow:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

## Running Tests

```bash
# Run only your own folder's tests (example):
pytest randre_fearon/tests/

# Run all tests during integration:
pytest
```

See [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md) before making your first commit.
