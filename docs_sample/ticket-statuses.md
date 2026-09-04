## Ticket Statuses

Every ticket is always in exactly one of four statuses.

### Open

The ticket has been created but no agent has started work on it. Tickets
created via email or the API always start as `Open`.

### In Progress

An agent is actively working the ticket. A ticket moves to `In Progress`
automatically the moment it is assigned to an agent.

### Waiting on Customer

The agent has asked the requester for more information and is blocked until
they respond. The SLA clock pauses while a ticket is in this status — see
[Escalation Rules](how-to-escalation-rules.md) for how the pause interacts
with priority deadlines. A ticket automatically reverts to `In Progress` when
the requester replies.

### Closed

The issue is resolved (or the requester confirmed it no longer needs action).
Closed tickets are read-only. Reopening a closed ticket creates a new linked
ticket rather than editing the closed one, so the original resolution record
is preserved.
