# Demo video script (about 3 minutes)

Goal: show a person and three AI agents completing a real maintenance investigation
**through Switch in Mattermost**, then the human approval workflow that follows.
All data is fictional. Never show `.local/` files or tokens on screen.

## Before recording (10 minutes)

1. Services up: the Switch stack (`docker ps` shows Switch, Gateway and Mattermost),
   the application database, the API on 8100 and `npm run dev` on 5173.
   `.venv/bin/python scripts/run_checks.py --run-id YOUR_INVESTIGATION_UUID` should report all checks passed.
2. Switch Console open and connected, with `pr-triage`, `pr-history` and `pr-vendors`
   running from `investigation.template.yaml`. Its activity view should be visible.
3. Browser windows, signed in before recording so no token is visible:
   - private window A: dashboard as `tenant`
   - window B: dashboard as `owner`
   - private window C: dashboard as `coordinator` (Robin)
   - tab D: http://localhost:8065, the `property-rescue-investigation` room, signed in as the human user
4. In the owner dashboard set the queue filter to **Submitted** to hide earlier test runs.
5. Increase browser zoom to about 125% for legibility.

## Shot list

| Time | Screen | Do | Say (suggested) |
| --- | --- | --- | --- |
| 0:00 | Title / README top | — | "Landlords and small property teams lose days on every repair: who fixed this before, is it under warranty, which vendor, what should it cost? Property Rescue puts a team of AI agents on that investigation, through Switch, while humans keep every decision." |
| 0:15 | A (tenant) | Report "Kitchen tap is dripping", plumbing, short description. Send. | "A tenant reports a problem. That's all they see: their request and its status." |
| 0:30 | B (owner) | Open the new request → **Acknowledge** → **Collect evidence**. Expand the vendors section. | "The owner collects evidence from the property's history, warranties and vendor directory. Every finding cites a source, and unknowns are labelled." |
| 0:50 | B → D | **Copy brief for Switch agents**, paste it as one message in the Mattermost room. | "Now the real work happens in Switch. I hand the brief to the agent team in our private room." |
| 1:00 | D + Console | Let it run (speed up 2–4× in editing). Point at `INV_ACK`, the targeted `INV_HISTORY_TASK` / `INV_VENDOR_TASK`, both results, then `INV_REPORT`. Briefly show Console's **Show activity** tool calls. | "pr-triage coordinates and hands tasks to the history and vendor specialists with Switch targeted messages. They answer in the same thread, and triage posts a cited report. No agent can contact anyone or spend anything: they only have Switch messaging tools." |
| 1:40 | B | **Sync agent discussion from Mattermost**. Open the `INV_REPORT`. Show the timeline gaining `collaboration.message` events. | "The conversation becomes part of the record: each agent post, linked to this investigation and timeline. The report is marked received, not verified. Humans judge it." |
| 2:00 | B | Propose **Contact vendor** citing `vendor:` evidence. Click **Execute** before approving → "Refused: Action has no current approval (HTTP 409)". **Approve revision 1** → **Execute** → "fictional – nothing sent". | "Nothing consequential happens without approval, and the backend enforces it, not the button. The approval is bound to this exact revision. Retries never execute twice." |
| 2:25 | C (Robin) | Queue: tick two apartment requests → title "Boiler outage" → coordinator Riley → **Create incident**. | "For teams: many tenants, one shared queue. The coordinator groups related requests into an incident. Each tenant's original complaint is preserved." |
| 2:40 | C | Open an incident request's action that Robin can't approve (or show the reassignment) → refusal shown; timeline shows `incident.coordinator_assigned` and `action.denied`. | "Only the incident's coordinator can approve, spending above the team limit needs the owner, and reassigning the incident revokes old approvals." |
| 2:55 | README "How Switch is used" + docs/CHECK_RESULTS.md | Scroll. | "Switch is the collaboration layer: without it there is no agent investigation. Everything here is reproducible from the repo, with all checks passing." |

## If something goes wrong while recording

- Agents silent: check Console shows the three agents running and that the message
  started with `@pr-triage INV_START`. Re-post only after checking room history.
- Sync returns 404: the brief for *this* investigation has not been posted yet.
- Sync returns 502 "HTTP 401": rerun `scripts/connect_mattermost.py` and restart the API.
- If a live run fails on camera, show the earlier verified run instead: the seeded
  "Fictional water issue" request (investigation `e0ecd9c3…`) already holds a real imported thread.
