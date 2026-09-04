## Assigning a Ticket

### Manual assignment

Open the ticket and use the **Assignee** dropdown in the right-hand panel.
![the Assignee dropdown](img/assignee-dropdown.png)
Only agents who are members of the ticket's team appear in the list. Assigning
a ticket automatically moves its status from `Open` to `In Progress` if it
was still `Open`.

### Auto-assignment

Teams can enable round-robin auto-assignment under **Team Settings > Routing**.
When enabled, every new ticket in that team's queue is assigned to the next
agent in rotation, skipping anyone marked "Away" in their agent status.
Auto-assignment does not consider current workload — it is a strict rotation,
not a load balancer.

### Reassigning

Reassigning a ticket does not reset its status or SLA clock. The SLA timer
started when the ticket was created (or last escalated — see
[Escalation Rules](how-to-escalation-rules.md)), not when it was assigned to
the current agent.
