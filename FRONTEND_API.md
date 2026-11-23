# Frontend integration contract

Base URL for local development: `http://127.0.0.1:8000`. Full request and response schemas are in `openapi.json` and the running `/docs`. No frontend has been built yet.

## Authentication

POST `/auth/login` with JSON `{"username":"...","password":"..."}`. Send the returned token as `Authorization: Bearer <access_token>` on authenticated requests. GET `/auth/me` identifies the account and role; POST `/auth/logout` revokes its session. A 401 requires login again. A 403 indicates insufficient permission. The backend enforces permissions regardless of which controls the frontend displays.

Roles: `manager`, `cashier`, `entry_clerk`, `preparation_display`, `customer_display`. Cashiers see their own orders; managers can review all orders. Display accounts must not reuse a manager or cashier token.

## Main workflows

1. Manager configures restaurant settings, province/tax rules, menu categories/items, recipes, promotions and combos. Fiscal connectors can remain disabled until credentials are available.
2. Entry clerk records stock, suppliers and purchase invoices. Manager approves stock adjustments/counts. Use `/inventory/invoices` for multi-line purchases and `/attachments/{entity}/{ident}` for receipt uploads.
3. Cashier calls POST `/orders/preview` for server-calculated totals, then POST `/orders` to confirm. Preview does not reserve stock. Confirmed orders retain pricing/tax snapshots.
4. POST `/orders/{ident}/payments` records payments; use `mixed` payment mode on an order intended for split cash/card payment. A tendered cash amount above the balance produces change. GET `/orders/{ident}/payments` provides payment status and outstanding balance.
5. POST `/orders/{ident}/status` advances `queued` to `preparing`, then `ready`, then `collected`. Unpaid preparation needs a manager exception and reason. GET `/orders` returns the FIFO queue and supports filters.
6. Manager handles refunds, cancellation, returned quantities and `/orders/{ident}/revision`. These operations retain original transaction history. A refund and a physical stock return are separate decisions.
7. GET `/orders/{ident}/receipt` returns printable HTML. Fiscal pending/test/verified states are distinct; never fabricate a government reference or QR code in the frontend.
8. Manager dashboards and exports live under `/reports`; inventory notifications, movement records and audit endpoints provide operational review.

## Displays

Use GET `/displays/customer` or `/displays/preparation` for initial state. GET `/displays/{screen}/events` streams updates over SSE. Use streaming `fetch` so the Authorization header is included; native EventSource cannot set that header. Reconnect after interruption and refresh the snapshot. Customer data contains only order codes and status. Preparation data includes food details without prices.

## Conventions

- All money is integer paisa; format it as PKR only at the UI boundary. Rates are basis points.
- Quantities are integer base units. Purchase units/conversions are explicit.
- Dates are Unix seconds, not JavaScript milliseconds. Restaurant timezone controls receipt and period-report display.
- Validation errors use FastAPI's `detail` response. Conflicts such as unavailable stock or uncertain fiscal submission usually return 409; display the server explanation and refresh state.
- Use server previews and totals for billing. Do not calculate a separate frontend tax amount or treat payment success as government submission success.
- Upload attachments as multipart form data; accepted formats are PDF, PNG and JPEG, up to 5 MiB.
- CORS allows localhost and 127.0.0.1 on port 3000 by default. Set `CORS_ORIGINS` before starting the API for other origins.

Live government acceptance remains pending credentials. Backend tests cover local behavior and mocked authority contracts.
