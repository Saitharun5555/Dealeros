# DealerOS

DealerOS is a full-stack reconciliation application for comparing transaction records from two systems.

## Technology

- Python 3.11+ with Django and Django REST Framework
- SQLite
- pytest and pytest-django
- React and Vite
- Plain CSS
- Decimal values for monetary calculations

## Folder structure

```text
dealeros/
  backend/
    config/
    reconcile/
      management/commands/
      migrations/
      tests/
    data/
  frontend/
  README.md
  DECISIONS.md
  DATA_ANALYSIS.md
  requirements.txt
  .gitignore
```

## Setup

From the `dealeros` directory:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

The project was developed with Python 3.13, but the assignment targets Python 3.11+.

### Database setup

```powershell
cd backend
py manage.py migrate
py manage.py import_data
```

Run the importer twice to verify idempotency. The second run should keep the database counts at 5 locations, 120 System A records, and 121 System B entries.

## Run the application

Backend:

```powershell
cd backend
py manage.py runserver
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Tests

```powershell
cd backend
py -m pytest -q
```

## API

The organization parameter is required:

- `GET /api/disagreements/?org=ORG-A`
- `GET /api/disagreements/?org=ORG-B`
- `GET /api/disagreements/?org=ORG-A&reason=MISSING_IN_B`
- `GET /api/disagreements/?org=ORG-A&sort=value`
- `GET /api/disagreements/?org=ORG-B&sort=-value`

Missing organization parameters return HTTP 400. Unknown organizations and reasons also return HTTP 400.

The response contains `reason`, `record_id`, `location`, `a_value`, `b_value`, and `difference`. Unknown values are JSON `null`.

## Organization isolation

The Location model, populated only from `locations.csv`, is the source of truth for organization ownership. API database queries filter by `location__org_id`. Cross-tenant mismatches are also split by ownership, and foreign locations and foreign record identifiers are redacted in the response.

The `org` parameter is only application-level data filtering. It does not authenticate a user. A production system should replace it with authenticated tenant claims and server-side authorization.

## Design summary

- System B is compared with System A `total_value`, not `base_value`.
- References are normalized and raw reference/value strings are preserved.
- Blank or invalid monetary values are NULL, never zero.
- Multiple B entries are accepted as a split only when all values are present and sum exactly to the A total.
- VOIDED A records do not generate MISSING_IN_B when there is no B entry.
- Cross-tenant mismatches show only each tenant's own side.

See `DECISIONS.md` and `DATA_ANALYSIS.md` for details.

## Project scope

DealerOS provides an import and reconciliation workflow for the provided
System A and System B CSV datasets. It imports locations and records,
normalizes supported reference and amount formats, compares System B against
System A `total_value`, exposes disagreement categories through a REST API,
and presents the results in an organization-filtered React table.

## Deliberately excluded features

- Authentication and authorization beyond organization query filtering
- A database-backed import audit UI
- User management, workflows, notifications, or write operations
- Production deployment, PostgreSQL configuration, or infrastructure automation
- Real-time synchronization or scheduled imports
- A distributed or multi-database reconciliation service
- Changes to the React/Vite frontend structure or visual design

The `org` request parameter is intentionally not authentication. Production
use would require authenticated tenant claims and server-side authorization.

## AI-agent workflow

The implementation was completed with a fact-grounded workflow:

1. Inspect the existing Django models, importer, comparison engine, API view,
   tests, CSV files, and documentation.
2. Reproduce or inspect each identified behavior before editing.
3. Make narrow source changes while preserving the existing Django/React stack.
4. Add or update focused tests for comparison, organization isolation,
   sorting, import behavior, and raw-value preservation.
5. Run the Django test suite, run the importer twice, and build the frontend.
6. Remove generated environments, dependency directories, caches, build output,
   temporary setup scripts, and stale execution logs from the submission package.

## Mandatory AI experience answers

**A. One thing the AI agent got wrong and how it was detected.**

The AI agent initially implemented sort=value and sort=-value using the absolute difference rather than the actual signed difference. I detected this while reviewing the assignment requirements and checking the API implementation. I corrected the sorting logic and updated the API tests to verify ascending and descending sorting using signed difference values.

**B. The part of the implementation that is least confident and why.**

The area I am least confident about is organization isolation, particularly cross-tenant records. The implementation relies on consistent organization ownership through Location records and carefully redacts foreign locations and identifiers. Although I have added tests for tenant isolation, I would want to review this further under authenticated, production-style tenant access before deploying it in a real environment.

**C. What would be improved first with another day.**

If I had another day, I would prioritize implementing authentication and server-side tenant authorization. Currently, the organization query parameter is used for filtering but does not authenticate or authorize users. Adding authenticated users with server-enforced organization membership would make the application more secure and suitable for production use.