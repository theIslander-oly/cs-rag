## Search Fields Reference

The fields available in Advanced Search (see
[Searching for Tickets](how-to-manual-search.md) for how to open the panel).

### Single-select fields

`status`, `priority`, `team`, `category` — pick exactly one value per search.

### Multi-select fields

`assignee`, `tag`, `requester` — pick any number of values; results match
tickets satisfying *any* of the selected values within that field (an OR,
not an AND).

### Date range fields

`created_at`, `closed_at`, `last_updated` — each accepts a from/to pair.
Leaving one side blank makes it open-ended.

### Fields not searchable via Advanced Search

Custom fields (see [Custom Fields](custom-fields.md)) are not filterable from
the Advanced Search panel in the current version — they can only be searched
via the quick search bar if their value appears in the ticket description, or
through the API's `/api/v1/tickets/search` endpoint, which does support
custom-field filters.
