## Custom Fields

Teams can define custom fields per category to capture structured data
beyond the default subject/description/priority set.

### Field types

- **Text** — free text, optional max-length validation
- **Number** — integer or decimal, optional min/max range
- **Dropdown** — a fixed list of options defined by the team admin
- **Checkbox** — boolean, useful for "customer notified" style flags
- **Date** — used for things like a hardware warranty expiry or a requested
  completion date

### Making a field required

Under **Team Settings > Custom Fields**, toggle **Required** on any field.
Required fields must be filled in before a ticket can move out of `Open`
status, and are enforced again at close time (see
[Closing a Ticket](how-to-close-ticket.md)) — except through the bulk-close
path, which does not check them.

### Field visibility

By default, custom fields are visible to agents only. Toggling **Visible to
requester** shows the field (and its current value) on the requester-facing
ticket page as well, which is useful for fields like "estimated completion
date" but not for internal-only fields like "root cause category."
