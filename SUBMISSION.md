# Submission — Property Rescue

**Track:** 01 — Best Business Workflow
**One line:** A team of AI agents investigates rental maintenance problems with a human through Switch, and every consequential step waits for backend-verified human approval.
**Repository:** [github.com/Satwik-Pothineni/property-rescue](https://github.com/Satwik-Pothineni/property-rescue) · **Demo video:** [youtu.be/py_b3An0K7A](https://youtu.be/py_b3An0K7A)

## Description

Independent landlords and small property-management teams handle every repair by
hand: reading the complaint, digging up past repairs and warranties, picking a
vendor, guessing a cost, chasing approvals. Property Rescue turns that into a
shared workflow between people and AI agents.

A tenant reports a problem. The owner or team coordinator collects evidence from
the property's history, warranties, vendor directory and planning allowances, then
hands a scoped brief to three agents in a private Mattermost room **through Switch**.
`pr-triage` coordinates and delegates to `pr-history` and `pr-vendors` with Switch
targeted messages. They reply in the thread, and triage posts a report that cites
every source and separates facts, guesses and missing information. The app imports
that thread into the request's record and live timeline.

Humans then propose actions (contact a vendor, schedule a visit, authorize
spending, close the request). Each needs an approval bound to its exact revision,
from someone with the right role: the owner, the incident's coordinator, or the
owner for spending above the team limit. The backend and database re-verify
before anything executes, and repeated or concurrent attempts execute once.
Teams get a shared queue and incidents that group related requests without
altering any tenant's original complaint.

## How Switch is used (central)

- The three agents run in official Switch Console (`investigation.template.yaml`), join a
  private Mattermost room through Switch's bridge, and collaborate only through
  Switch room and messaging tools (`connect_to_room`, `read_context`, `post_message`, `send_targeted_message`).
- A human starts the run in team chat (`INV_START`). Agents hand off work to each
  other and report back in that thread: one person and three agents completing a
  real task together.
- Without Switch there is no agent investigation, no human/agent conversation and no
  report; the app would only show raw evidence.
- Verified live: the run `e0ecd9c3-a72f-4cae-84e7-144c39d000dc` (8 Mattermost posts,
  every cited source checked against the packet) is imported into the app. See
  `docs/CHECK_RESULTS.md` and `PROGRESS.md`.

## Built with

Switch Console 0.40.1 and its bundled Mattermost 11.9 · Python 3.15, FastAPI, SQLAlchemy,
Alembic, PostgreSQL 18 · React 19, TypeScript 7, Vite 8, Vitest.

## Verification

`scripts/run_checks.py`: 63 backend tests (real PostgreSQL) and 11 frontend tests,
individual and team end-to-end scenarios, live Switch thread import, duplicate-sync,
and real Mattermost failure handling (bad token, unreachable). The latest run passed
15/15. The project also builds and passes from a clean copy of the repository files.

## Honest limits

The demo video's agent thread is the verified live run `3aafb708-fb03-4fcc-a2bb-dfaa460c8edd`
(started with `INV_START`); the one-line `investigate` command shown starts the same agents and workflow.
Fictional data only (DoorLoop deferred). Vendor, calendar and payment execution is a
labelled fictional adapter. Agents cannot call the API; a human relays the brief and
syncs the report with a button. Local demo authentication only.

## Requirement checklist (checked 2026-11-07 against wemakedevs.org/hackathons/switch and /rules)

| Requirement | Status |
| --- | --- |
| Switch central; README shows how it is used | README "How Switch is used" section and diagram |
| A team-chat workflow where at least one agent and one person complete a real task through Switch | Live three-agent investigation in Mattermost, started and reviewed by a human |
| Switch setup and agent workflow built during Nov 4–7 | Earliest project file Nov 4 08:41 IST; Switch stack Nov 4 09:20 IST; investigation template and live run Nov 7 ≈02:30–02:45 IST |
| Reproducible from a clone | Clean copy of the repo files: `uv sync --locked`, 59 tests, `npm ci`, 11 tests, build all passed |
| Demo video showing Switch use | https://youtu.be/py_b3An0K7A |
| Submit by Nov 7, 11:59 PM IST (1:29 PM EST) | **Pending** — needs a public repository and the submission form |
| AI use permitted; entrant understands the work | Architecture and decisions documented in README and PROGRESS.md |
| Original work; complies with third-party licenses | Dependencies pinned in `uv.lock` / `package-lock.json`; no license chosen for this repo yet (entrant's decision) |
