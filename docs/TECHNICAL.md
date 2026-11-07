# Property Rescue: technical reference

Start with the [README](../README.md) for setup and the demo walkthrough.

**AI-assisted maintenance operations for independent landlords and property
management teams, built on Switch.** A tenant reports a problem. A team of three
AI agents investigates it together with a human in a Mattermost room through
Switch, and posts a cited report. Humans then approve every consequential step.
Vendor contact, scheduling, spending and closure run only after the backend
verifies a valid approval.

Built for the Flip the Switch hackathon (Nov 4–7, 2026), Track 01: Business
Workflow. All people, properties, vendors and costs are fictional.

**Demo video:** https://youtu.be/py_b3An0K7A

## How Switch is used

The investigation is the **real task that a person and AI agents complete
together through Switch**:

```text
Owner/coordinator (dashboard)          Mattermost room (private)               Switch Console agents
──────────────────────────────          ─────────────────────────               ─────────────────────
1. Collect evidence (API, DB)
2. Copy brief ───────────────────────▶ human posts  INV_START <run id>  ──────▶ pr-triage (coordinator)
                                        INV_ACK, INV_HISTORY_TASK  ◀──────────  targeted messages via Switch
                                        INV_VENDOR_TASK            ──────────▶  pr-history, pr-vendors
                                        INV_*_RESULT               ◀──────────  specialists reply via Switch
                                        INV_REPORT (cited, no actions) ◀──────  pr-triage
3. Sync agent discussion ◀──────────── API reads the thread (GET only), links posts to the investigation
4. Propose → approve → execute  (role rules + backend approval checks; agents can never execute)
```

- **Switch is the collaboration layer.** The three agents (`investigation.template.yaml`)
  run in official Switch Console, join a private Mattermost room through Switch's
  bridge, and hand work to each other with `switch.send_targeted_message`.
  Without Switch there is no agent investigation, no human/agent conversation
  and no report: the app would only collect raw database evidence.
- **Humans stay in charge.** Agents get a scoped, fictional evidence packet and only
  Switch messaging tools. No shell, no credentials, no execution. Their report is imported as
  labelled, untrusted text and never triggers anything.
- **The conversation becomes records.** Each agent post is stored with its Mattermost post
  ID, sender (agent or human) and tag, and appears on the request's live timeline
  next to evidence, proposals, approvals and refusals.
- **Verified live:** a real three-agent run (`INV_START` → `INV_ACK` → two targeted tasks
  → two results → `INV_REPORT`) with every cited source ID checked against the packet,
  then imported into the app ([docs/CHECK_RESULTS.md](CHECK_RESULTS.md), [PROGRESS.md](../PROGRESS.md)).

## What it does

| Mode | Flow |
| --- | --- |
| Individual landlord | Tenant reports → owner acknowledges → evidence + Switch agent investigation → owner approves an action → execution → closure, with a live timeline |
| Property team | Many tenants → shared queue → coordinator groups requests into an incident (originals preserved) → only the incident's coordinator approves; spending above the team limit needs the owner |

Approvals bind to the exact action revision and a database-computed hash. They
expire after 24 h and are rechecked at execution, as is the approver's current
authority. PostgreSQL triggers independently refuse execution without a matching
approval. Repeated or concurrent attempts execute once, and every refusal is logged.

**Stack:** Python 3.15, FastAPI, SQLAlchemy, Alembic, PostgreSQL 18 · React 19 + TypeScript 7 (Vite 8) ·
Switch Console 0.40.1 with its bundled Mattermost 11.9 (official local Compose stack).

## Quick start (reproduce from a clone)

Prerequisites: Docker Desktop, [uv](https://docs.astral.sh/uv/) 0.13.7, Node ≥ 22.12 (tested on 26.5), and
[Switch Console 0.40.1](https://github.com/sandbox-quantum/switch) with a model provider (tested with Codex).

```sh
uv sync --locked
uv run --locked python scripts/prepare_switch.py
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway up -d
uv run --locked python scripts/prepare_app.py
docker compose --env-file .local/app/.env up -d --wait
uv run --locked --env-file .local/app/.env alembic upgrade head
uv run --locked --env-file .local/app/.env python -m property_rescue.seed
```

Switch: in Console choose **Connect to an existing server** (`http://localhost:8000`), import
`investigation.template.yaml`, click **Use template** (Codex, Local, Mattermost).
It creates the private room `property-rescue-investigation` with the three agents.
Then let the API read that room and start everything:

```sh
uv run --locked python scripts/connect_mattermost.py
uv run --locked --env-file .local/app/.env uvicorn property_rescue.api:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

In a second terminal run `cd frontend && npm ci && npm run dev`, then open http://127.0.0.1:5173
and sign in with a value from `.local/app/demo-tokens.json` (`owner`, `coordinator`,
`coordinator_two`, `member`, `tenant`). Mattermost is at http://localhost:8065.
Generated secrets stay in ignored `.local/` files.

Verify everything (in a third terminal, with the API running):

```sh
.venv/bin/python scripts/run_checks.py --run-id YOUR_INVESTIGATION_UUID
```

Replace `YOUR_INVESTIGATION_UUID` with the UUID in the brief of a completed real
Switch investigation. On a fresh installation, complete that conversation first;
the checker does not create or simulate an agent report.

It runs the backend and 11 frontend tests, both end-to-end scenarios, the live
Switch thread import, duplicate-sync and real Mattermost failure checks, and writes
[docs/CHECK_RESULTS.md](CHECK_RESULTS.md). The demo walkthrough is in [DEMO.md](../DEMO.md).

## Honest status and limits

- Agent reasoning happens in Switch Console with the user's model provider; the app does not call an LLM itself.
- Vendor contact, scheduling and payment are a **labelled fictional adapter** (`delivery: not_sent`). Closure is a real state change.
- Agents cannot call the API; a human relays the brief and syncs the report. Sync is manual (a button), not a webhook. It walks channel history and refreshes
  edited or removed posts; audit events retain the change history without keeping retracted text.
- Local demo bearer tokens, not production auth. DoorLoop integration is deferred; all data is seeded fiction.
- An execution interrupted mid-call stays "outcome unknown" for manual reconciliation; it is never re-run blindly.

The sections below are the detailed per-checkpoint guides.

## Try the dashboard and team mode (Checkpoint 5)

One-time setup after pulling (from the project root, with the uv `PATH` exports
from "Start or reproduce Checkpoint 2"):

```sh
uv run --locked --env-file .local/app/.env alembic upgrade head      # team policy + collaboration tables
uv run --locked --env-file .local/app/.env python -m property_rescue.seed   # adds coordinator_two (Riley) and her token
.venv/bin/python scripts/connect_mattermost.py                     # optional: lets the API read the Switch room
(cd frontend && npm ci)                                             # Node 26; exact pinned versions
```

`connect_mattermost.py` logs in as the local human Mattermost account and stores
its session token plus the investigation channel ID in `.local/app/.env` (0600,
ignored). The API uses it for GET requests only. Rerun it if sync reports HTTP 401.

Run the API (restart it after the steps above) and the dashboard in two terminals:

```sh
uv run --locked --env-file .local/app/.env uvicorn property_rescue.api:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
cd frontend && npm run dev        # http://127.0.0.1:5173
```

Sign in by pasting a value from `.local/app/demo-tokens.json`. Try `owner`
(individual cottage + team apartments), `coordinator` (Robin), `coordinator_two`
(Riley), `member` and `tenant`. Use a private window per identity to compare.

- **Tenant:** report a problem, see your own requests' status. No queue or approvals.
- **Coordinator:** shared queue for the team's property. Tick requests, give a
  title and coordinator, **Create incident**; reassign or unlink from the incident card.
- **Any manager:** open a request → **Collect evidence** → findings with source IDs
  → **Copy brief for Switch agents** → paste it in the private investigation room →
  **Sync agent discussion from Mattermost** to import the agents' tagged replies.
  Propose actions citing evidence; approve, reject and execute; the live timeline
  updates as you and others act. Refusals from the backend show as "Refused: …".

Automated scenario (18 checks, plus one when Mattermost is configured; through the dashboard proxy):

```sh
.venv/bin/python scripts/demo_team_workflow.py http://127.0.0.1:5173/api
```

| Endpoint | Purpose |
| --- | --- |
| `GET /queue?status=` | Shared queue: originals with property, tenant, incident, evidence and action counts |
| `GET/POST /incidents` | List; create from request IDs with a coordinator (`Idempotency-Key`) |
| `PUT/DELETE /incidents/{id}/requests/{request_id}` | Link or unlink a request (originals unchanged) |
| `PUT /incidents/{id}/coordinator` | Reassign the human coordinator |
| `GET /properties/{id}/staff` | Team coordinators and members |
| `GET /requests/{id}/investigations` | Investigations for a request, with agent-review state |
| `POST /investigations/{id}/collaboration/sync` | Import the Switch thread for this run from Mattermost |
| `GET /investigations/{id}/collaboration` | Imported agent/human messages |

Owners and coordinators manage incidents; members cannot. Imported agent text is
displayed as untrusted data, labelled agent or human, and never triggers actions:
`agent_review: report_received` means an INV_REPORT arrived, not that it is correct.

Frontend checks: `cd frontend && npm run typecheck && npm test && npm run build`.
Versions (verified on npm 2026-11-06, exact pins in `frontend/package-lock.json`):
React 19.3.1, TypeScript 7.0.2, Vite 8.3.6 with @vitejs/plugin-react 6.2.1,
Vitest 5.1.0 with jsdom 31.0.0, Testing Library react 16.3.3 / dom 10.4.2 /
user-event 14.6.8. All declare support for the installed Node 26.5.0; Node 26 LTS
began at 26.13.0, so upgrading Node is recommended but not required.

## Try approvals and the owner timeline (Checkpoint 4)

After pulling these changes, apply the migration and restart the API (`Ctrl+C`
the old uvicorn, then run the start command in "Start or reproduce Checkpoint 2"):

```sh
uv run --locked --env-file .local/app/.env alembic upgrade head
```

Then run the whole tenant → owner scenario. It prints PASS/FAIL per check and
the owner's timeline:

```sh
.venv/bin/python scripts/demo_owner_workflow.py            # default http://127.0.0.1:8100
```

It creates one new fictional request on the cottage and closes it through an
approved action; seeded requests are untouched. Tokens are never printed.

To click through it yourself at http://localhost:8100/docs (authorize as `owner`):

1. **POST /requests/{id}/investigations** on a request, keep the run `id` and an
   evidence `id` from its sections (e.g. `vendor:...`).
2. **POST /requests/{id}/actions** with a fresh `Idempotency-Key`:

   ```json
   {"investigation_id": "<run id>", "rationale": "Fictional: plumbing vendor in packet.",
    "evidence_ids": ["vendor:<id>"],
    "details": {"kind": "contact_vendor", "vendor_id": "<id>", "message": "Please quote the tap repair."}}
   ```

3. Try **POST /actions/{id}/execution** now: **409**, and a `action.denied` entry
   appears in **GET /requests/{id}/timeline**.
4. **POST /actions/{id}/decision** with `{"decision": "approved", "revision": 1,
   "details_hash": "<from the action>"}`, then execute again: **200**,
   `status: executed`, `result.delivery: not_sent`. Repeating with the same key
   returns the same result; a new key returns **409**.
5. Edit it with **PUT /actions/{id}** (`expected_revision` + new details): the
   revision increments, the approval is invalidated and execution is refused
   until the new revision is approved.

| Endpoint | Purpose |
| --- | --- |
| `POST /requests/{id}/actions` | Propose an action citing investigation evidence (`Idempotency-Key`) |
| `GET /requests/{id}/actions`, `GET /actions/{id}` | Read actions and the current revision's decision |
| `PUT /actions/{id}` | Revise; requires `expected_revision`; invalidates prior approval |
| `POST /actions/{id}/decision` | Approve/reject the exact `revision` + `details_hash` shown |
| `POST /actions/{id}/execution` | Execute with an `Idempotency-Key`; re-verifies approval and authority |
| `GET /requests/{id}/timeline?after=N` | Ordered, gapless owner timeline (managers only) |
| `GET /requests/{id}/timeline/stream` | Live Server-Sent Events; resumes with `Last-Event-ID` |

Action kinds and who may approve **and** execute them:

| Kind | Owner | Team coordinator | Team member |
| --- | --- | --- | --- |
| `contact_vendor`, `schedule_visit`, `close_request` | yes | yes (team properties) | propose only |
| `authorize_spend` | yes | up to the team's limit (demo: USD 500); none if unset | propose only |

For a request linked to an incident, only **that incident's coordinator** has
coordinator authority; other coordinators act as members. Reassigning the
coordinator makes the previous coordinator's unexecuted approvals unexecutable.

Approvals bind to the actor, their authority, the action revision and a hash the
**database** computes over details, rationale and evidence. They expire after 24
hours. At execution the backend rechecks the approval, its expiry, the approver's
current authority and the executor's authority. PostgreSQL triggers independently
refuse execution without a matching unexpired approval, any edit without a new
revision, any change to decisions or timeline entries, and closing a request
except through an executing approved `close_request`. Tenants never see actions
or the internal timeline; they see their request's status.

Execution is **fictional for the demo**: `FictionalDemoExecutor` records the
approved action and contacts no vendor, calendar or payment system. Closure is a
real internal state change. A real provider adapter would receive the execution
idempotency key. Execution stuck in `executing` (crash mid-call) is reported as
"outcome unknown" and needs manual reconciliation; it is never re-run blindly.

## Try the investigation (Checkpoint 3)

The evidence service is implemented, and a live three-agent Switch review has
been verified. `ready_for_review` means evidence collection finished; agent
conclusions stay in Switch and are not written back to the database.

For the prepared demo:

1. In Switch Console import `investigation.template.yaml`, click **Use template**,
   and choose Codex, Local and Mattermost. It creates a **private** room with
   `pr-triage`, `pr-history` and `pr-vendors`. Keep Console open.
2. Open **http://localhost:8065/switch/channels/property-rescue-investigation**.
   If a link uses `mattermost:8065`, use localhost instead. The live bridge's
   public URL was updated to `http://localhost:8065` on November 6.
3. Open `.local/app/investigation-brief.txt`, copy the entire contents and send
   it as one message in that private room. The prepared packet contains fictional
   records and no credentials. The file is local, not part of source control.
4. Expect `INV_ACK`, both specialist tasks, `INV_HISTORY_RESULT`,
   `INV_VENDOR_RESULT`, then `INV_REPORT` in the same thread. Findings should
   cite source IDs and distinguish facts, uncertainty, missing data and proposals.
   A blocked run must say `INV_BLOCKED`, not invent successful tool results.
5. Confirm the final report and both specialist activities through **Show activity**.
   Record the run/root/post IDs and tool evidence in PROGRESS.md before declaring
   the checkpoint complete. A template or a packet by itself is not live AI evidence.

To investigate another request, authorize as its owner or assigned team staff in
http://localhost:8100/docs and use the following routes:

| Endpoint | Purpose |
| --- | --- |
| `POST /requests/{request_id}/investigations` | Start evidence collection with a UUID `Idempotency-Key`; repeats return the existing run |
| `GET /investigations/{run_id}` | Retrieve persisted evidence, source IDs and ordered step activity |
| `POST /investigations/{run_id}/retry` | Retry failed evidence steps using a fresh UUID `Idempotency-Key`; repeating that key does not rerun failures |
| `GET /investigations/{run_id}/brief` | Export the authorized plain-text packet to paste into the private Switch room |

Tenants and unrelated owners/staff cannot use these routes. Export is a deliberate
human action: verify the private room's audience before sharing a property packet.
No owner API token or database credentials are supplied to the agents.

Evidence tools in `property_rescue/investigation.py` are replaceable Python
collectors (`EvidenceTool`); default collectors read the real application database.
They are deterministic tools, **not mock AI agents**. Triage, history/warranty and
vendor reasoning are performed by actual Console agents communicating through
Switch. They receive a dated snapshot, not unrestricted database access.

- Triage records the tenant's category without claiming a diagnosis or urgency.
- History reads prior work and same-property same-category requests. This matching
  rule is explicitly tentative, not proof of a common cause. Warranty dates are
  checked separately from coverage and asset match.
- Vendor review supplies directory candidates with unverified availability and
  qualifications. Fictional plumbing planning allowances are **USD 150–300** for a
  minor tap/valve repair, excluding major replacement, hidden damage, tax and
  emergency charges. They expire December 1, 2026. They are not vendor quotes or
  approved spending. Other categories/expired records produce “estimate unavailable”.
- Each finding references its evidence source IDs. Missing evidence is a finding;
  a tool error makes the run `partial`. Successful steps survive selective retries,
  and failed tool SQL rolls back to a savepoint. Provider error bodies are not stored.
- Activity is persisted when synchronous collection commits; no live streaming or
  background worker is claimed. A database outage returns an explicit API error.
  Retry with the same creation key after service recovery. A fresh key makes a new
  snapshot; successful sections of an existing run are not silently refreshed.
- For agent failures, inspect Switch activity and retry with `@pr-triage INV_RETRY
  <run-id>` in the original thread. This relies on agent history and human review;
  there is no durable exactly-once guarantee for LLM room replies or automatic
  agent timeout supervisor. Backend evidence retries are independently tested.
- The template grants no external connections or agent-management capability and
  leaves permission bypass off. Its tool-use instructions are not a hard runtime
  sandbox. Do not approve non-messaging tool requests. No vendor, scheduling,
  spending, closure or execution integration exists in this application.

After upgrading an existing Checkpoint 2 setup, run `alembic upgrade head` and
`python -m property_rescue.seed` with `.local/app/.env` as in the startup commands
below, then restart the API. Migration `84836fd49c2c` adds investigations and
planning allowances without rewriting original requests. New seeds have a fixed
fictional complaint date; existing seed rows remain untouched.

No new packages were installed for Checkpoint 3. Switch's pinned
[template contract](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/docs/TEMPLATES.md)
and [agent protocol](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/docs/official/internals/agent-protocol.md)
were rechecked. `send_targeted_message` is supported; the experimental task API
is not used. The template's `channel_private`, `owner-agents`, `auto_approve: false`
and `can_manage_agents: false` fields are documented official fields.

## Try the maintenance API

The API is running at **http://localhost:8100/docs**. This page lets you try the
backend without a frontend.

1. Open `.local/app/demo-tokens.json` privately in your editor. Copy the value
   beside `tenant` (without the quotation marks).
2. On the API docs page click **Authorize**, paste that value, and authorize.
3. Open **GET /properties**, click **Try it out**, then **Execute**. Copy a property
   `id` from the result.
4. Open **POST /requests**, click **Try it out**, and enter a fresh UUID in
   `idempotency-key`. Generate one with `uv run --locked python -m uuid`.
   Use the property ID in this body:

   ```json
   {
     "property_id": "<copy a property id from GET /properties>",
     "title": "Kitchen tap is dripping",
     "description": "Fictional demo: the cold tap drips overnight.",
     "category": "plumbing"
   }
   ```

5. Click **Execute**. A new request returns HTTP **201**. **GET /requests** shows
   your saved requests. Sending the same body with the same key returns the same
   request with **200**; changing the body but reusing the key returns **409**.

To try the owner view, use **Authorize → Logout**, then authorize with the `owner`
token from that same local file. You can now read the owner's requests and property
history. Keep tokens out of screenshots and chat.

## Start or reproduce Checkpoint 2

From the project root, use uv **0.13.7**. On this machine the executable is already
at `.local/uv-aarch64-apple-darwin/uv`; make it available in the current terminal:

```sh
export PATH="$PWD/.local/uv-aarch64-apple-darwin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --locked
```

First setup only: `uv run --locked python scripts/prepare_app.py`. It creates
`.local/app/.env` with a random database password and refuses to overwrite an
existing file. This machine is already prepared.

Start Docker Desktop, then run:

```sh
docker compose --env-file .local/app/.env up -d --wait
uv run --locked --env-file .local/app/.env alembic upgrade head
uv run --locked --env-file .local/app/.env python -m property_rescue.seed
uv run --locked --env-file .local/app/.env uvicorn property_rescue.api:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

If port 8100 is already in use by this API, use the running instance. `Ctrl+C`
stops the foreground API. `docker compose --env-file .local/app/.env stop` stops
only the application database and preserves data. Never regenerate the database
password while reusing its existing volume.

The application uses its own PostgreSQL 18.6 container, database and volume on
loopback port **55432**. Switch's separate provider database is unchanged.
Migrations are explicit; API startup never creates or changes tables. The seed
command can be repeated: stable IDs avoid duplicates and existing records/states
are not overwritten. Demo tokens are generated randomly once and stored locally;
only their SHA-256 hashes are stored in the database.

## Checkpoint 2 roles and data

| Actor | Read access | Write access in this checkpoint |
| --- | --- | --- |
| Tenant | Active rented properties and their own requests | Submit to an active tenancy |
| Owner | Owned properties, their requests, history, warranties, vendors and incidents | Acknowledge requests on owned properties |
| Team coordinator | Assigned team's managed properties and records | Acknowledge requests for that team |
| Team member | Assigned team's managed properties and records | None |
| Unrelated account | No access to another owner's/team's records | None |

Bearer tokens resolve to database users. Supplying a user ID or role header cannot
change identity. Inactive users and revoked tokens cannot authenticate. This is
explicit **local demo authentication**, not production account provisioning or SSO.
Local database credentials have development administration rights for migrations;
a production deployment needs separate migration/runtime roles, HTTPS and a full
identity lifecycle. No production deployment is part of this checkpoint.

Seeded records: eight fictional users, one team, two team memberships, three
properties, four tenancies, four original requests, one coordinator-owned incident,
and three records each for vendors, maintenance history and warranties. Two
separate tenant requests are linked to the same incident. A fifth fictional
request was added on this machine by the HTTP smoke check. Vendor emails use
`example.invalid`; nothing sends email or contacts a vendor.

The only request transition implemented is **submitted → acknowledged**.
Acknowledgement is repeatable and does not authorize work or close a request.
PostgreSQL rejects edits to original complaint content, identity, property,
creation time and idempotency key. Incident references must match the request's
property, and an incident must have a coordinator belonging to its property's
team. Incident linking is represented in the data model and fixtures; the human
coordination/grouping workflow belongs to Checkpoint 5.

| Endpoint | Purpose |
| --- | --- |
| `GET /me` | Inspect the authenticated identity |
| `GET /properties` | List accessible properties |
| `POST /requests` | Submit with a UUID `Idempotency-Key` header |
| `GET /requests?limit=50&offset=0` | List scoped requests (limit 1–100) |
| `GET /requests/{id}` | Read one scoped request |
| `PUT /requests/{id}/acknowledgement` | Owner/coordinator acknowledgement |
| `GET /properties/{id}/history` | Prior work and costs for investigation |
| `GET /properties/{id}/warranties` | Fictional warranty evidence |
| `GET /properties/{id}/vendors` | Property-scoped fictional vendor directory |
| `GET /properties/{id}/incidents` | Read seeded incident/coordinator records |

Configuration is in `database.py`, relational records in `models.py`, API contracts
in `schemas.py`, authorization/business operations in `service.py`, and thin routes
in `api.py`. The existing Switch connectivity modules remain separate.

## Checkpoint 2 verification and dependency sources

```sh
uv run --locked --env-file .local/app/.env python -W error::ResourceWarning -m unittest discover -s tests -v
uv run --locked --env-file .local/app/.env alembic check
uv pip check
```

The Checkpoint 2 suite originally had **30 passing tests**. The current suite
has **41 passing tests**, including 28 PostgreSQL integration tests in disposable
random schemas, one application configuration test, and the 12 existing
connectivity tests. Tests cover authorization, persistence across app instances,
four concurrent submissions with one idempotency key, immutable source records,
foreign-key/role constraints, repeated seed runs, and migration down/up. They do
not change the public demo schema. Without `APP_DATABASE_URL`, the 28 PostgreSQL
tests explicitly skip; a skipped suite is not checkpoint verification.

Verified against official metadata/docs on 2026-11-04:

| Selected dependency | Compatibility/source |
| --- | --- |
| FastAPI 0.162.0 | [PyPI metadata](https://pypi.org/pypi/fastapi/0.162.0/json): Python >=3.10, Starlette >=0.46, Pydantic >=2.9 |
| SQLAlchemy 2.1.8 | [Official releases](https://www.sqlalchemy.org/download.html), Python >=3.11; [psycopg dialect](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg) |
| Psycopg binary 3.3.8 | [Metadata](https://pypi.org/pypi/psycopg/3.3.8/json); [supported Python/PostgreSQL](https://www.psycopg.org/psycopg3/docs/basic/install.html) includes Python 3.15 and PostgreSQL 18 |
| Pydantic 2.14.2 | [Metadata](https://pypi.org/pypi/pydantic/2.14.2/json); pins pydantic-core 2.50.2 |
| Alembic 1.20.1 | [Metadata](https://pypi.org/pypi/alembic/1.20.1/json): SQLAlchemy >=2.0; [migration guide](https://alembic.sqlalchemy.org/en/latest/tutorial.html) |
| Uvicorn 0.54.0 | [Metadata](https://pypi.org/pypi/uvicorn/0.54.0/json): Python >=3.10; no optional server extras |
| HTTPX2 2.16.0 (tests) | [Metadata](https://pypi.org/pypi/httpx2/2.16.0/json); selected Starlette 1.10.0's TestClient prefers HTTPX2 and warns on legacy HTTPX |
| PostgreSQL 18.6-alpine | Latest stable supported major/minor from [PostgreSQL](https://www.postgresql.org/support/versioning/) and [official image](https://hub.docker.com/_/postgres). Version 19 was a release candidate, not selected. |

`uv.lock` fixes all resolved transitive versions, including Starlette 1.10.0.
Python remains pinned at 3.15.2. Compatibility was checked by resolution, `uv pip
check`, the complete PostgreSQL suite and live HTTP verification—not inferred
solely from version numbers. The initial HTTPX 0.28.1 test adapter was replaced
with HTTPX2 to remove Starlette's deprecation warning.

## Checkpoint 1 connectivity reference

Status: Checkpoint 1 connectivity proof completed on 2026-11-04. The live
Mattermost thread passed API verification, and the user supplied Switch activity
reports for both agents. Evidence and limitations are recorded in PROGRESS.md.
The steps below reproduce the proof; test fixtures alone are not live evidence.

## Selected integration

Use official **Switch Console** to run two agents from
`connectivity.template.yaml`. Console owns registration, runtime, SSE consumption,
heartbeats, reconnection and HTTP operations. Python only reads a Mattermost
thread and checks its correlation evidence. No custom chat service or speculative
Switch SDK is installed. The connectivity proof itself uses only the Python standard library.

The path to demonstrate is:

```text
Human in Mattermost -> Switch Mattermost bridge -> coordinator in Console
coordinator -> Switch targeted message -> worker in Console
worker -> Switch targeted reply -> coordinator -> Switch -> Mattermost thread
```

Switch creates a Mattermost bot identity for each agent. The bridge connects
outward to Mattermost; this local proof needs no internet-facing webhook or tunnel.
Agent transport uses bearer-authenticated SSE down and HTTP operations up.
Registration tokens and agent API keys have different purposes. Console manages
them; never put them in the proof environment. The documented task-event API is
not ready for use, so the template uses `send_targeted_message` instead.

`PR_CONNECT`, `PR_ACK`, `PR_TASK`, `PR_RESULT`, `PR_DONE` and the UUID are this
project's proof markers, **not Switch protocol message types**. Switch's room,
message, thread and connection identifiers are separate from Mattermost post IDs;
do not assume equality between them.

## Verified versions and official sources (2026-11-03)

| Component | Selection and compatibility basis |
| --- | --- |
| Python | 3.15.2, latest stable listed by [Python](https://www.python.org/downloads/); pinned in `.python-version`. Standard library only. Tests executed on this version. |
| uv | 0.13.7, [official stable release](https://github.com/astral-sh/uv/releases/tag/0.13.7). The preinstalled 0.11.32 could not locate Python 3.15.2. A project-local 0.13.7 successfully synchronized it. |
| Switch Console | [0.40.1 stable release](https://github.com/sandbox-quantum/switch/releases/tag/switch-console-v0.40.1). Installation and provider sign-in remain manual. |
| Switch Core, Gateway, setup | 0.31.0, explicitly paired with Console by its [app identity](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/console/apps/switch-console-desktop/src/shared/app-identity.ts). |
| Mattermost | 11.9.0, pinned by the [official bundled Compose](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/console/apps/switch-console-desktop/src/main/core/managed-switch-server/resources/standalone-docker-compose.pinned.yml). Do not independently upgrade it: Console depends on its UI contract. Runs as linux/amd64 on this Apple Silicon host. |
| Provider database | `postgres:16-alpine`, as required by the same official stack. This is provider infrastructure, not the Checkpoint 2 application database. Upstream floats this tag; record image digests when reproducing. |
| Local container tooling | Existing Docker Desktop 4.98.0, Engine 29.9.2, Compose 5.6.1; actual startup verified. No Docker upgrade performed. |

Contract references:

- [Hackathon](https://www.wemakedevs.org/hackathons/switch): Switch must be central; a real person and agent must collaborate. Mattermost is supported.
- [Repository](https://github.com/sandbox-quantum/switch) and [quickstart](https://docs.switchagents.ai/switch-rooms/getting-started).
- Release-pinned [agent protocol](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/docs/official/internals/agent-protocol.md), [Mattermost connection](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/docs/official/deploy/messaging-apps/mattermost.md), [template language](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/docs/TEMPLATES.md), and [official two-agent example](https://github.com/sandbox-quantum/switch/blob/switch-console-v0.40.1/examples/agent-templates/triage-pair.template.yaml).
- [Mattermost API](https://docs.mattermost.com/api): the checker uses `GET /api/v4/users/username/{username}` and `GET /api/v4/posts/{post_id}/thread`. The latter requires channel read access; bearer tokens remain local.
- [uv locked synchronization](https://docs.astral.sh/uv/concepts/projects/sync/).

## Reproduce the Python setup

Install uv 0.13.7 using its official release. In this workspace it is available at
`.local/uv-aarch64-apple-darwin/uv`; substitute that path for `uv` below if needed.
Use project-local caches to keep installation within the workspace:

```sh
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$PWD/.local/python"
uv sync --locked
uv run --locked python -W error::ResourceWarning -m unittest discover -s tests -v
```

The HTTP transport test binds a temporary loopback port. A sandbox must allow that
operation. All automated conversations are explicitly fixtures, not live evidence.

## Official local stack

Docker Desktop must be running, with ports 3000, 8000, 8065 and 5432 free.
Network access to GitHub, GHCR and Docker Hub is required. Images consume several
GB; Mattermost requires amd64 emulation on Apple Silicon.

```sh
uv run --locked python scripts/prepare_switch.py
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway up -d
```

The preparation script downloads Console 0.40.1's official bundled Compose and
environment example, selects its supported Core version, generates unique secrets,
and saves the files under ignored `.local/switch/` with restrictive permissions.
It refuses to overwrite an existing environment. On this machine preparation and
startup are **already complete**. Do not regenerate credentials on existing volumes.

Check readiness:

```sh
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8065/api/v4/system/ping
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway ps -a
```

`init-db` and `setup` should exit successfully; the other four services stay up.
Internal callback traffic uses `http://switch:8081` on the Docker network for
Mattermost interactive actions. Host bindings are loopback only. The official
configuration enables bot creation and access tokens. No cloud Switch account is
required for this self-hosted environment.

To stop without deleting data:

```sh
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway stop
```

## Manual steps to complete the real proof

1. Install [Switch Console 0.40.1 for Apple Silicon](https://github.com/sandbox-quantum/switch/releases/download/switch-console-v0.40.1/switch-console-arm64.dmg).
   Sign into a supported installed agent provider using Console's Agent providers
   instructions. A provider subscription or API access is needed; configure it
   locally, never in chat or tracked files.
2. In Console choose **Connect to an existing server**, not a second local server.
   In the **Server address** field shown by Console 0.40.1, enter
   `http://localhost:8000`. If your version shows separate fields, the Gateway
   URL is `http://localhost:3000` and API URL is `http://localhost:8000`.
   Open `.local/switch/.env` privately in your editor for `GATEWAY_ADMIN_EMAIL`
   and `GATEWAY_ADMIN_PASSWORD`. The official setup links this account to the
   seeded Mattermost user. Confirm that link and the active Mattermost connection.
3. Open `http://localhost:8065` in your browser (if Console opens
   `https://mattermost:8065`, replace it with `http://localhost:8065`; the internal
   Docker hostname does not work in the browser) and sign in using `MATTERMOST_USER` and
   `MATTERMOST_USER_PASSWORD` from that same local file. These are the human
   development account credentials, not the Mattermost admin account.
4. On Console's Templates page use the YAML in `connectivity.template.yaml`.
   Select your authenticated provider and the bundled Mattermost bridge. Create
   both agents and the room. Keep Console running and confirm both sessions are
   available. Template execution was verified during the recorded live proof.
5. Generate a new run identifier with `uv run --locked python -m uuid`. As the
   human, post `@pr-coordinator PR_CONNECT <uuid>` in the created Mattermost channel.
   Expect separate ACK, targeted TASK, worker RESULT and coordinator DONE posts
   in that root's thread. Do not manually create bot responses to satisfy the check.
6. Copy `.env.example` to `.env`, restrict it with `chmod 600 .env`, and fill in
   the human username, root post ID from its permalink, and UUID. Verify actual
   bot usernames against the member list. Put a local Mattermost access/session
   token with access to this channel in `MATTERMOST_TOKEN`. Token creation may
   require the local admin to enable permission for the human account. Do not
   paste any token here. The Python reader makes GET requests only, although the
   token itself may have broader permissions.
7. Run the checker:

   ```sh
   uv run --locked --env-file .env python -m property_rescue.proof
   ```

8. Record the output's run, channel, root, sender and post IDs in PROGRESS.md.
   Also inspect both **real Console sessions** and record the Switch room ID,
   both agent/session IDs, received source message/thread IDs and matching
   targeted tool calls/results. Correlate using the UUID and timestamps. The
   checker deliberately returns `switch_runtime_verified: false`: Mattermost
   bot posts alone cannot prove the Switch path. Do not mark the checkpoint
   passed until both forms of evidence exist.

## Failure behavior and limits

Missing configuration fails before network access. Tokens are hidden from settings
representations; redirects are refused, errors omit response bodies, and evidence
omits message content. HTTP authentication/permission errors and unavailable
services produce nonzero exits. The verifier rejects duplicate or missing stages,
wrong senders, bot-as-human identities, edited/deleted posts, cross-thread posts,
missing recipient mentions and out-of-order timestamps. Start a fresh UUID after
a failed/ambiguous run. It does not post or automatically retry writes.

The template asks agents to ignore repeated stages using room history; this is
not a durable exactly-once execution guarantee. Runtime retries and duplicate
delivery behavior remain to be observed live. Instructions limiting agent tools
are not a security boundary; use an isolated working directory and provider
permissions. No maintenance execution tools are supplied in this checkpoint.

Never publish raw container logs or `.env` files. Inspect and redact any captured
runtime evidence before adding it to progress. `.local`, `.venv`, caches and local
environment files are ignored. AGENTS.md and PLAN.md remain unchanged.
