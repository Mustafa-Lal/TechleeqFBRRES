# FIRRES restaurant backend

FastAPI backend for a single restaurant, with cashier, manager, entry clerk, preparation display and customer display accounts. Local backend scope includes FR-001 through FR-094. No frontend, online ordering, table management or deployment is included.

## Start locally

Use Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.bootstrap
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The bootstrap command prompts for the first manager account; there are no default credentials. Open http://127.0.0.1:8000/docs for interactive API schemas. Log in at `/auth/login`, then send `Authorization: Bearer <access_token>`. Managers create other accounts at `/users`.

## Implemented functionality

- Accounts, role restrictions, password changes/resets, deactivation and revocable sessions.
- Menu categories, item codes, variants, prices, availability and ingredient recipes.
- Scheduled or permanent promotions and combos, priorities, stacking and authorized price overrides.
- Order previews, confirmation, FIFO queues, stock reservation, preparation/ready/collected states, cancellation and linked replacement orders.
- Cash/card/split payments, cash change, payment references, partial/full refunds, returned quantities, printable receipts and cash-shift reconciliation.
- Inventory categories, suppliers, unit conversions, multi-line purchase invoices, attachments, payments, partial returns, weighted-average costs, stock counts, approved adjustments and recurring low-stock notifications.
- Expense categories, payments, reversals and filters; purchase costs are recognized through ingredient consumption rather than counted twice as expenses.
- Period dashboards, item/combo rankings, sales trends, expenses, supplier balances, tax collected and CSV exports. Reports flag incomplete ingredient costing.
- Authenticated live SSE displays. Customer displays expose order codes and status only; preparation displays include food details without prices.
- Actor audit logs, record change history, linked transactions and restaurant settings.
- Province-specific tax snapshots, fiscal adapters, pending invoice processing, credit notes and uncertain-outcome reconciliation.

## Data conventions and storage

Money uses integer paisa: `100` means Rs1. Percentages use basis points: `1000` means 10%. Stock uses integer base units, such as grams or bottles; purchase conversions multiply into base units. API dates are Unix seconds. Receipts and period reports use the configured timezone, default `Asia/Karachi`.

SQLite defaults to `restaurant.db`; set `DATABASE_PATH` to change it before starting. Business records are typed JSON documents with separate account, session and audit tables. Write transactions serialize stock and payment changes. This is a local, single-restaurant implementation; distributed deployment and load certification are outside this delivery.

Back up the database before upgrades. For transactions from the first prototype, run `python -m app.migrate` with the intended `DATABASE_PATH`. This idempotent migration creates a `.pre-v2.bak` backup and marks unavailable historic cost details rather than inventing them. Keep database and backup files private.

## Province and fiscal configuration

Managers select `punjab` (PRA), `sindh` (SRB), `khyber_pakhtunkhwa` (KPRA), `balochistan` (BRA), or `islamabad` (FBR) at `/settings/tax`. Supply the applicable official rate, source, effective date, registration, cash/card rates, inclusive/exclusive pricing and discount-tax treatment. No tax rates are guessed. There is no generic government rate-discovery endpoint implemented; official rates are entered and versioned by the manager. Orders retain their original tax rule and connector for later submission and credit notes.

Configure `/fiscal/connectors` with an authority, environment prefix, mode, transport and optional official service classification code. Credentials are environment variables and are not returned by the API:

| Authority | Transport | Variables appended to the prefix |
|---|---|---|
| KPRA | cloud | `_NTN`, `_POS_ID`, `_KEY` |
| SRB | cloud | `_NTN`, `_POS_ID`, `_USERNAME`, `_PASSWORD` |
| PRA | cloud | `_POS_ID`, `_TOKEN` |
| PRA, BRA, FBR | local registered IMS component | `_POS_ID` |

For example, prefix `FISCAL_BRANCH` reads `FISCAL_BRANCH_POS_ID`. PRA/BRA/FBR also require the official service classification code. Local IMS must be installed and registered separately. KPRA currently requires live mode and approved credentials; its endpoint does not provide a separately verified test-mode contract here. Use different prefixes when registration identities change.

Submit invoices at `/fiscal/orders/{ident}/submit` and credits at `/fiscal/credits/{ident}/submit`. `/fiscal/process-pending` processes a bounded invoice batch. Set `FISCAL_WORKER_ENABLED=true` to process pending invoices every ten seconds; it is off by default. Credit submissions remain explicit.

Successful invoices are not submitted again. Explicit rejections can be corrected and retried. Timeouts and ambiguous responses become `unknown`, blocking blind retries. Managers record authority-check evidence through the reconciliation endpoint. Operator-reconciled outcomes are distinguished from successful API responses. Test submissions are labeled separately and do not produce live government verification QR codes.

Unsupported payment mappings fail explicitly; KPRA/SRB mixed-payment submissions need a verified mapping. SRB discounts must use its supported tax-before-discount treatment. Connector configuration does not establish the legal correctness of a tax rate.

**Live government acceptance testing is deferred until credentials are available, as requested.** All five adapters have mocked contract coverage, not live certification. In particular, the installed BRA/FBR IMS version, registrations, rate rules and accepted payloads must be checked against the restaurant's actual authority environment before real fiscal use.

Contract references: [KPRA documentation](https://posregistration.kpra.gov.pk/docs), [PRA technical specification](https://e.pra.punjab.gov.pk/templates/Technical_Specification_Software_Fiscal_Device_1.2_PRA.pdf), [PRA IMS manual](https://e.pra.punjab.gov.pk/templates/POS_COMPONENT_and_eIMS_User_Manual.pdf), [SRB API specification](https://www.srb.gos.pk/srb/wp-content/uploads/2026/01/New-POS-API-Document-V1.pdf), [BRA IMS guide](https://ebra.com.pk/public/assets/indexpageassets/pdfs/imsguide.pdf). FBR uses the legacy local IMS contract and requires version confirmation during live acceptance.

## Verification and frontend handoff

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary databases and mocked external responses. The test fixture blocks unmocked external POST requests. `QA_REQUIREMENTS_REPORT.md` is regenerated from actual test outcomes and `tests/requirements_map.json`. Each of the 94 requirements is linked to one or more scenario tests; these are grouped tests, not 94 separate test functions. Live government acceptance is excluded from the pass claim.

See `FRONTEND_API.md` for frontend conventions and `openapi.json` for the generated endpoint/schema contract. The running `/openapi.json` remains the authoritative schema. CORS defaults to `http://localhost:3000`; set comma-separated `CORS_ORIGINS` for the frontend origin.
