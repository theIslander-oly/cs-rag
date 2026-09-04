## Creating a Ticket

Tickets are the base unit of work in TicketFlow. Any request — a bug report, an
access request, a hardware issue — starts as a ticket.

### From the dashboard

1. Click **New Ticket** in the top-right corner of the dashboard.
   ![the New Ticket button](img/new-ticket-button.png)
2. Choose a **Category** (Hardware, Access, Software, Other). The category
   determines which queue the ticket lands in and which default priority is
   applied — see [Priority Levels](priority-levels.md) for the mapping.
3. Fill in **Subject** and **Description**. Description supports Markdown.
4. Optionally attach files by dragging them into the **Attachments** panel.
   ![the Attachments drop zone](img/attachments-panel.png)
5. Click **Submit**. The ticket is created with status `Open` and appears in
   the relevant team's queue within a few seconds.

### From email

Any email sent to `helpdesk@yourcompany.com` is automatically converted into
a ticket. The email subject becomes the ticket subject, the email body
becomes the description, and any attachments are carried over. The category
defaults to `Other` and must be set manually by the first agent who picks it
up.

### From the API

```
POST /api/v1/tickets
{
  "subject": "...",
  "description": "...",
  "category": "hardware"
}
```

Requires an API key with the `tickets:write` scope. See the API reference
for authentication details.
