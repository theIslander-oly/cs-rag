## Closing a Ticket

### Standard close

Open the ticket, select a **Resolution** reason from the dropdown (Fixed,
Duplicate, Not Reproducible, Won't Fix, Requester Cancelled), add a closing
comment, and click **Close Ticket**.
![the Close Ticket button](img/close-ticket-button.png)
The status moves to `Closed` (see [Ticket Statuses](ticket-statuses.md)) and
the ticket becomes read-only.

### Closing with a custom field unset

If the ticket's category has any required custom fields (see
[Custom Fields](custom-fields.md)) and one is still empty, TicketFlow blocks
the close action and highlights the missing field rather than closing with
incomplete data.

### Bulk closing

From a filtered ticket list, select multiple tickets with the checkboxes and
choose **Close Selected** from the bulk-actions menu. Bulk close always uses
the resolution reason "Fixed" and skips the custom-field requirement check —
use it only for genuinely resolved, low-stakes tickets, since it bypasses the
same validation the single-ticket close path enforces.
