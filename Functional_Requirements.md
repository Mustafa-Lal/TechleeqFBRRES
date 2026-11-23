# Restaurant Management System — Functional Requirements

## 1. System scope

FR-001. The system shall support restaurant staff in managing menus, promotions, cashier orders, payments, stock purchases, inventory consumption, expenses, and operational reporting.

FR-002. The initial system shall support one restaurant with three staff roles: Manager, Cashier, and Entry Clerk. Restricted display accounts shall provide access to the order screens.

FR-003. Customer online ordering, delivery platform integration, table management, and deployment or hosting management shall be outside the initial scope. Live order screens shall display orders entered by cashiers.

## 2. Accounts and access

FR-004. Staff shall log in using individual accounts. Each recorded action shall identify the responsible user.

FR-005. Managers shall create, activate, deactivate, and assign roles to staff and display accounts, and reset their passwords. Deactivated accounts shall retain their historical records.

FR-006. Managers shall access menu management, promotions, inventory, expenses, reports, staff administration, and all order records.

FR-007. Cashiers shall create orders, accept payments, view their orders, update fulfillment status, and reprint receipts. They shall not change menu prices, promotion rules, inventory purchase costs, or financial reports.

FR-008. Entry Clerks shall manage stock categories, stock items, suppliers, purchases, and permitted inventory entries. They shall not manage selling prices, promotions, payments, staff accounts, or profit reports.

FR-009. Managers shall review and correct Entry Clerk records through recorded adjustments or reversals. Clerks shall not delete posted purchases or expenses.

FR-010. Display accounts shall log in only to their assigned screen. A preparation display account shall access order preparation details; a customer display account shall access order codes and public status only. Neither shall access payments, reports, staff data, or management functions.

FR-011. Users shall be able to log out and change their own passwords. Only authorized roles shall perform each restricted action.

## 3. Food categories and menu items

FR-012. Managers shall create, edit, arrange, activate, and deactivate menu categories such as Appetizers, Drinks, and BBQ.

FR-013. Managers shall create and edit menu items with a unique item code, name, category, description, selling price, and availability status. Item images shall be optional.

FR-014. Managers shall define item sizes or variants with separate selling prices and ingredient quantities, where applicable.

FR-015. Cashiers shall see only active, available items and current effective selling prices when creating new orders.

FR-016. Managers shall mark an item temporarily unavailable and restore it when available. Changes shall affect new order entries without rewriting existing order records.

FR-017. Categories and items referenced by historical transactions shall be deactivated rather than deleted. Moving or renaming an item shall preserve its historical sales records.

## 4. Discounts and combinations

FR-018. Managers shall create percentage or fixed-amount discounts for selected items, categories, or eligible order totals.

FR-019. Each discount shall have a name, eligibility rules, start date and time, and end date and time, or be explicitly permanent. Managers shall activate, deactivate, and edit discounts.

FR-020. The system shall automatically apply eligible active promotions during order pricing and stop applying them after expiry.

FR-021. Managers shall define whether promotions may combine and their precedence when multiple promotions apply. The system shall prevent accidental duplicate discounting and discounts exceeding the eligible amount.

FR-022. Managers shall create combos containing specified quantities of menu items or variants, with a combo name and a fixed selling price.

FR-023. Combos shall support scheduled start and end times or permanent availability. A combo shall be unavailable if a required component is unavailable.

FR-024. Combo sales shall consume the stock of their component recipes. Reports shall show combo sales and identify component quantities without counting combo revenue twice.

FR-025. Cashiers shall not enter arbitrary discounts or override prices. A Manager shall authorize exceptional discounts or price overrides and record the reason.

FR-026. Receipts and order records shall show the applied discount or combo price. Subsequent promotion changes shall not alter finalized orders.

## 5. Cashier orders and queue

FR-027. Cashiers shall create orders by selecting menu items or combos, entering quantities, and adding item-level or order-level preparation notes.

FR-028. Before confirmation, cashiers shall edit quantities, remove lines, and review the subtotal, discounts, tax, and payable total.

FR-029. Each confirmed order shall receive a unique internal order number, a short customer-facing order code, creation and confirmation times, and the creating cashier's identity. Public codes shall be unique among active orders.

FR-030. The system shall persist confirmed orders and their line items, quantities, prices, discounts, tax breakdown, totals, payment records, and status history.

FR-031. Confirmed orders shall follow the fulfillment states Queued, Preparing, Ready, and Collected. Cancelled shall be a separate terminal state. Payment status shall be tracked independently.

FR-032. Confirmed orders shall enter the preparation queue in first-come, first-served order using confirmation time. Cashiers shall see their active orders with the oldest uncompleted order first; managers shall see all orders.

FR-033. Cashiers shall mark orders Preparing, Ready, and Collected. The system shall record the acting user and time for every transition and prevent invalid transitions or accidental repeated actions.

FR-034. An order shall normally be fully paid before entering preparation. A Manager shall be able to authorize preparation of an unpaid order, with a recorded reason.

FR-035. Editing or cancelling a confirmed order shall require Manager authorization and a reason. Changes shall retain an audit history, update the preparation display, and reconcile affected stock, payments, and tax records.

FR-036. Cashiers shall search their order history by order code, date, and status. Managers shall additionally filter by cashier and review all historical orders.

## 6. Live order displays

FR-037. A dedicated preparation screen shall show all Queued and Preparing orders in first-come, first-served order, including order code, item names, quantities, preparation notes, status, and elapsed waiting time. It shall not show prices or financial totals.

FR-038. The preparation screen shall update when orders are added, changed, cancelled, or moved to a different status. Ready and Collected orders shall leave its active preparation list.

FR-039. A separate customer-facing screen shall show only order codes grouped under Preparing and Ready. Queued and Preparing orders shall both appear under the public Preparing group.

FR-040. The customer-facing screen shall not show item names, quantities, notes, prices, payment details, customer details, or staff details.

FR-041. When a cashier marks an order Ready, its code shall move to Ready on the customer-facing screen. Collected and Cancelled orders shall disappear from that screen.

FR-042. Display accounts shall be read-only. Order status changes shall be performed through an authorized Cashier or Manager account.

## 7. Payments and receipts

FR-043. Cashiers shall record cash and card payments, including the amount received, payment method, timestamp, and optional card transaction reference. The system shall not require storage of full card numbers or card security codes.

FR-044. The system shall support split payments, calculate cash change, show outstanding balances, and mark an order Paid only when its payable amount is covered. Change shall not be recorded as revenue.

FR-045. Recording a card payment shall document the payment received through an external terminal; direct payment-terminal processing shall be outside the initial scope.

FR-046. Cashiers shall issue and reprint receipts containing restaurant details, order code, date and time, purchased items, quantities, prices, discounts, tax, total, payment method, and cash change where applicable. Reprints shall be identified as copies.

FR-047. Managers shall authorize full or partial refunds against original payments and specify a reason. The system shall retain the original sale and separately record refunded amounts, items, users, and timestamps.

FR-048. Refunds and cancellations shall not automatically return prepared food to stock. Managers shall specify whether eligible unused stock is restored or consumed stock remains recorded as waste.

FR-049. Cashiers shall open and close cash shifts, recording opening float and counted closing cash. The system shall calculate expected cash from opening float, cash receipts, cash refunds, and recorded drawer movements, and report any difference to the Manager.

## 8. Tax and fiscal invoices

FR-050. Managers shall configure the restaurant's applicable tax authority, registration details, officially applicable tax rates, effective dates, and supporting rule references. Rules shall accommodate payment-method differences where applicable.

FR-051. The system shall calculate tax using the configured applicable rules, including discount treatment, tax-inclusive or tax-exclusive pricing, and required rounding. Each finalized invoice shall retain the rules and amounts used at the time of sale.

FR-052. Where an authority provides a supported rate lookup service, the system shall support obtaining applicable rates through that service. Otherwise, an authorized Manager shall maintain rates from official rules. Cashiers shall not choose arbitrary tax rates.

FR-053. For the restaurant's selected authority, the system shall submit required invoice details using registered credentials, record its response and official reference, and produce the prescribed verification QR code and receipt particulars.

FR-054. The system shall track fiscal submissions as Pending, Submitted, or Failed. Unconfirmed submissions shall not be presented as government-confirmed invoices.

FR-055. Managers shall view failed or pending submissions, inspect the failure reason, and retry eligible submissions with duplicate protection. Refunds and cancellations of reported invoices shall generate the authority-required adjustment or credit note.

## 9. Stock items, suppliers, and purchases

FR-056. Inventory categories shall be separate from customer-facing menu categories. Entry Clerks and Managers shall create and maintain stock categories such as Meat, Vegetables, Beverages, and Packaging.

FR-057. Each stock item shall have a unique code, name, category, base measurement unit, current quantity, minimum stock threshold, and active status. Purchase costs shall be separate from menu selling prices.

FR-058. The system shall support quantities measured by count, weight, or volume and defined conversions such as kilograms to grams or cartons to individual units.

FR-059. Entry Clerks shall create and maintain suppliers with a name and optional contact details.

FR-060. Entry Clerks shall record purchases with supplier, purchase date, supplier invoice reference, stock items, purchased quantities and units, unit costs, discounts, applicable purchase taxes or charges, total cost, and payment status. Supporting receipt attachments shall be optional.

FR-061. Posting a purchase receipt shall increase received stock and record its acquisition cost. Reusing the same supplier invoice reference for the same supplier shall trigger a duplicate warning.

FR-062. Purchases shall support Paid, Partially Paid, and Unpaid statuses, with payment dates, amounts, methods, and outstanding supplier balances.

FR-063. Supplier returns and purchase corrections shall create linked reversal or adjustment records rather than erase original transactions. Inventory quantities, costs, and outstanding balances shall update accordingly.

FR-064. Managers shall record opening stock and its cost. Stock items referenced by transactions shall be deactivated rather than deleted.

## 10. Recipes, stock consumption, and alerts

FR-065. Managers shall define recipes linking each menu item or variant to stock items and quantities required per serving. Directly resold items shall support a one-unit stock deduction without a multi-ingredient recipe.

FR-066. Confirming an order shall reserve the required stock. Moving the order to Preparing shall convert that reservation into stock consumption. The system shall prevent duplicate consumption when status actions repeat.

FR-067. Cancelling an order before preparation shall release reserved stock. Cancelling after preparation shall follow the Manager's recorded stock disposition and shall not silently restore consumed ingredients.

FR-068. Available stock shall equal stock on hand minus active reservations. The system shall warn cashiers when an order exceeds available ingredients and require Manager authorization to proceed with a shortage.

FR-069. Entry Clerks shall record stock counts and proposed adjustments. Managers shall approve adjustments for wastage, spoilage, damage, counting differences, or corrections, with quantity, reason, responsible user, and date.

FR-070. Every receipt, reservation, consumption, release, supplier return, wastage, and approved adjustment shall be traceable in stock movement history.

FR-071. When available stock reaches or falls below its minimum threshold, the system shall create an in-app notification for Managers and add the item to a low-stock list showing available quantity, unit, and threshold.

FR-072. Low-stock alerts shall remain active until replenishment or correction resolves the shortage. The system shall avoid repeated identical unread alerts and shall notify again if the item becomes low after recovery.

## 11. Expenses and cost records

FR-073. Entry Clerks and Managers shall record operating expenses such as rent, utilities, wages, maintenance, and cleaning, with category, date, description, amount, payee, payment method, and payment status. Supporting attachments shall be optional.

FR-074. Managers shall manage expense categories and review expenses by date, category, payee, payment status, and entering user.

FR-075. Stock purchases shall appear in purchase and cash-outflow records. They shall not also be counted as operating expenses when calculating profit; inventory cost shall enter profit calculations through recognized consumption or loss.

FR-076. Managers shall correct posted expenses through linked adjustments or reversals, retaining original records and reasons.

## 12. Manager dashboard and reports

FR-077. Managers shall view a dashboard with date filters and default views for today, this week, and this month.

FR-078. The dashboard shall show order count, net sales excluding sales tax, discounts, refunds, tax collected, payments by method, outstanding order balances, operating expenses, gross profit, and operating profit.

FR-079. Best-selling item reports shall rank items by quantity and net sales. Cancelled lines shall be excluded and returned quantities shall reduce applicable totals. Combo and component reporting shall avoid duplicate revenue.

FR-080. The system shall calculate inventory consumption cost using moving weighted-average purchase cost and retain the cost assigned to each consumption transaction. Later purchase price changes shall not rewrite historical order costs.

FR-081. Net sales shall equal finalized sales after discounts and sales returns, excluding collected sales tax. Gross profit shall equal net sales minus the cost of sold items. Operating profit shall equal gross profit minus operating expenses and separately recognized inventory losses, without counting the same cost twice.

FR-082. Recoverable purchase taxes, where applicable, shall be tracked separately from inventory or expense cost. The Manager shall configure their treatment according to applicable rules.

FR-083. Profit reports shall identify missing recipe costs, uncosted opening stock, and other incomplete cost records so that incomplete profit figures are visible to Managers.

FR-084. Managers shall view sales trends, item and category performance, combo performance, promotion usage, cancelled orders, refunds, stock balances, purchase totals, supplier balances, expense breakdowns, cash-shift differences, and pending fiscal submissions.

FR-085. Dashboard totals shall link to their supporting transactions. Reports shall support date filtering and export to CSV or printable output.

## 13. Record history and administrative controls

FR-086. The system shall retain an audit history for menu price changes, promotion changes, account changes, authorized overrides, order edits, status changes, payments, refunds, purchases, expenses, stock adjustments, and tax configuration changes.

FR-087. Audit entries shall identify the user, action, timestamp, affected record, and relevant previous and new values. Managers shall be able to search and review these entries.

FR-088. Transaction references shall remain linked across orders, payments, fiscal submissions, refunds, inventory movements, purchases, and expenses so Managers can trace each reported amount to its source.

FR-089. Managers shall maintain restaurant receipt details, business timezone, currency, and order-code settings. Scheduled promotions, transaction timestamps, and daily reports shall use the configured restaurant timezone.

## 14. Province selection and billing authority

FR-090. Managers shall select the restaurant's operating province or tax jurisdiction. The system shall map supported jurisdictions to their configured tax authority and billing connector. Cashiers, Entry Clerks, and display accounts shall not change this setting.

FR-091. Before enabling live fiscal submission, the Manager shall configure the selected authority's required restaurant registration details, POS identification, credentials, and applicable tax rules. Selecting a province alone shall not establish registration or determine all applicable tax rates.

FR-092. New invoices shall use the active jurisdiction configuration. Each finalized invoice shall preserve its jurisdiction, tax authority, tax rule version, amounts, and fiscal submission reference. Retries, refunds, and credit notes shall use the original invoice's authority even after the restaurant's configuration changes.

FR-093. Unsupported jurisdictions or incomplete connector configurations shall be clearly identified. The system shall not silently route invoices to another authority or claim successful government submission. Test responses shall be explicitly identified and shall not constitute live fiscal confirmation.

FR-094. Changes to jurisdiction, registration, and tax configuration shall be audited with the responsible Manager and effective time. The system shall validate connector readiness before activating live submission.
