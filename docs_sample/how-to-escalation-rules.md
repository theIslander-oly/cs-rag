## Escalation Rules

Escalation exists to make sure a ticket doesn't sit unanswered past its SLA
deadline (see [Priority Levels](priority-levels.md) for the deadlines
themselves).

### How escalation triggers

If a ticket's response SLA elapses while it is still `Open` or `In Progress`,
it automatically escalates one level (P3 → P2 → P1) and is reassigned to the
team lead's queue. Escalation only fires on elapsed *response* time, not
*resolution* time — a ticket an agent is actively working stays where it is
even past the deadline, as long as the first response was on time.

### Escalation and Waiting on Customer

A ticket in `Waiting on Customer` status does not escalate, because its SLA
clock is paused (see [Ticket Statuses](ticket-statuses.md)). If the requester
replies and the ticket reverts to `In Progress` with the deadline already in
the past, it escalates immediately on the next status change rather than
waiting for the next SLA check.

### Manual escalation

Any agent can manually escalate a ticket one level using the **Escalate**
button, regardless of SLA status. Manual escalation requires a reason, which
is logged on the ticket's timeline and visible to the requester.

### Where escalated tickets show up

An escalated ticket appears in the team lead's **Escalations** queue, which
is separate from their normal assigned-tickets view, and triggers a
notification via whatever channel the team lead has configured (email, Slack,
or both) under **Personal Settings > Notifications**.
