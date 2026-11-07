# Property Rescue — progress

## Current state — 2026-11-06

**Checkpoint 6 complete except the user-owned submission steps.** Both modes run
end to end; `scripts/run_checks.py` passed **15/15** (59 backend + 11 frontend
tests, both scenarios, live Switch thread import, duplicate sync, real Mattermost
failure handling) and is recorded in `docs/CHECK_RESULTS.md`. A clean copy of the
repo files builds and passes. README, DEMO.md and SUBMISSION.md are written.
Remaining (user): record the demo video, publish the repository, submit by
**Nov 7 11:59 PM IST (1:29 PM EST)**. See "Checkpoint 6 report".
Historical reports below retain their dates.

### Inspection findings

- Workspace: `/Users/satwik/Desktop/Property Rescue`.
- The directory was empty, including hidden entries, at inspection.
- No Git repository is initialized (`git status --short` reported that this is not a Git repository).
- No application code, dependency manifests, lockfiles, configuration, seed data, tests, or existing project instructions were present.
- No dependencies were installed and no external services were contacted or validated.

### Files created

- `AGENTS.md` — project rules, product requirements, engineering constraints, and checkpoint reporting requirements.
- `PLAN.md` — requirements, six-checkpoint task breakdown, acceptance criteria, and Checkpoint 1 prerequisites.
- `PROGRESS.md` — inspected baseline, verification status, blockers, and next steps.

Existing files modified or deleted: none.

### Verification performed

- `pwd` confirmed the workspace location.
- `rg --files` found no files (exit status 1); `ls -la` confirmed the directory was empty.
- `git status --short` exited 128 because there is no Git repository; this is an observed baseline, not a passing check.
- Documentation reviewed for alignment with the requested modes, architecture, approval rules, checkpoints, and implementation stop condition.
- Application tests: not run; no application or test suite exists. No integration success is claimed.

## Checkpoint status

| Checkpoint | Status | Evidence / remaining work |
| --- | --- | --- |
| 1. Switch and Mattermost connectivity | Complete — connectivity proof | Real five-stage thread verified via API; both agents’ Switch activity reports supplied by user; 12 tests passing. |
| 2. Models, APIs, seeded history | Complete | Real PostgreSQL persistence and migrations, fictional seeds, scoped API access; 30 tests passed and live HTTP smoke check passed. |
| 3. Agent investigation | Complete | Evidence pipeline and 41 tests pass; real three-agent Switch exchange verified via Mattermost API with valid citations; user-supplied Switch activity reports. |
| 4. Approvals and owner workflow | Complete | 52 tests (real PostgreSQL) and live 19-check HTTP scenario passed; vendor/calendar/payment execution is a fictional adapter. |
| 5. Team coordination and dashboard | Complete | 59 backend + 11 frontend tests; live 18/18 team scenario via dashboard proxy; live Mattermost sync of the real Switch thread. |
| 6. Integration tests, demo, submission | Complete — submission pending (user) | run_checks 15/15; clean-copy reproduction; README/DEMO/SUBMISSION written; video, public repo and form remain. |

## Initial Checkpoint 1 blockers and prerequisites (historical)

- User review of the initial documents is required before implementation by the explicit task instruction.
- The exact Switch provider, official integration documentation, and hackathon-specific requirements have not been supplied or verified.
- Switch and Mattermost development access, credentials, target channel, permissions, and networking have not been established.
- Dependency versions and compatibility have not been researched; official verification is required before installation.

See PLAN.md for the complete connectivity task breakdown and acceptance criteria. Keep credentials out of this document.

## Original next steps after review (historical)

1. Confirm the intended Switch integration and consult official documentation for Switch, Mattermost, and required dependencies.
2. Establish authorized development access and define the real connectivity proof.
3. Implement only the minimal Checkpoint 1 scaffold and adapters, then run automated checks and real connectivity verification.
4. Update this document with exact changed files, test commands/results, integration evidence, blockers, and next steps at checkpoint completion.

## Future checkpoint update format

Record checkpoint and date, delivered behavior, changed files, exact test commands and results (including failures/skips), live integration evidence without secrets, blockers/limitations, and next steps. Do not mark a checkpoint complete until its acceptance criteria have evidence.

## Checkpoint 1 report — 2026-11-03

### Delivered and verified

- Read all three planning documents and reviewed the official hackathon page.
  Identified `sandbox-quantum/switch`, its Console, agent protocol, Mattermost
  bridge, template language and official Compose deployment. Sources and selected
  compatibility constraints are linked in README.md.
- Contrary to the historical baseline, Git and an untracked Python/template/test
  scaffold were already present at the start of this implementation turn. Preserved
  and reviewed those files; did not reinitialize Git or claim authorship of them.
  There are currently no tracked files or commits. No files were staged or committed.
- Adopted the official two-agent Console template approach. The task-event API is
  documented as not ready; the proof uses supported targeted room messages instead.
  Python provides a read-only Mattermost transcript validator, not a replacement
  agent runtime. Template execution remains unverified until Console is configured.
- Prepared and started the release-pinned official development stack, with random
  local credentials in ignored `.local/switch/.env` (mode 0600). Provider Postgres
  exists only for Switch/Mattermost, with no application models or database.
- Verified configuration and failure handling, duplicate/incorrect proof rejection,
  HTTP contract behavior, redirect rejection and sanitized output using offline
  fixtures and a local HTTP test server. Fixed leaked HTTP error resources exposed
  by Python 3.15 warnings.
- No Checkpoint 2–6 features, FastAPI server, React, SQLAlchemy or maintenance
  modules were added.

### Files

Created this turn:

- `README.md`: verified contract/source/version notes, setup, live proof procedure,
  credential handling, stop command and limitations.
- `scripts/prepare_switch.py`: fetch official pinned environment/Compose files,
  generate secrets without printing them, refuse existing environment overwrite.

Changed this turn:

- `property_rescue/messaging.py`: close HTTP error responses before raising a
  sanitized integration error.
- `PROGRESS.md`: current state and this report. AGENTS.md and PLAN.md unchanged.

Existing scaffold reviewed and retained:

- `.env.example`, `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`.
- `connectivity.template.yaml` (two official-runtime agents and one room).
- `property_rescue/__init__.py`, `config.py`, `proof.py`, `messaging.py`.
- `tests/test_connectivity.py`.

Ignored local artifacts: uv executable, downloaded Python, `.venv`, cache,
official Compose and generated provider environment under `.local/`.

### Dependencies and versions

- Zero third-party Python runtime or test packages; standard-library unittest.
- Downloaded project-local uv **0.13.7** after checking its official stable release.
  Preinstalled uv **0.11.32** could not locate the pinned Python release.
- Downloaded and successfully ran **CPython 3.15.2**, the verified latest stable.
  Existing manifest permits `>=3.13,<3.16`; only 3.15.2 was tested.
- Official Console **0.40.1** selects Core/Gateway/setup **0.31.0** and bundles
  Mattermost **11.9.0**, with **postgres:16-alpine**. Console itself is not installed.
  Compatibility is taken from Console's release source, not independently latest
  container versions. Existing Docker Desktop **4.98.0**, Engine **29.9.2** and
  Compose **5.6.1** successfully started the stack.
- Image digests actually pulled (upstream database tag floats):

```text
postgres@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab
mattermost/mattermost-team-edition@sha256:1c538cf33c2144ba2c825571cd414aaaebf8d8c231d4b18081b811cd0ca0ef2a
ghcr.io/sandbox-quantum/switch-core@sha256:03b2ea9caa38f235878f3d872ca99dee74c6bda7a731ea01a209edc739699c1d
ghcr.io/sandbox-quantum/gateway@sha256:f9049a07c35d0e17253116fa0b2bca9872005bb06e38735a7a52093963732079
ghcr.io/sandbox-quantum/setup@sha256:4e046b650cc79fb8a1d3495e3393278b3658ca538f4ece6eae89caf033f79e27
```

### Exact checks and outcomes

Commands executed from the project root:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv sync --locked
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked python -W error::ResourceWarning -m unittest discover -s tests -v
.venv/bin/python scripts/prepare_switch.py
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway up -d
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8065/api/v4/system/ping
curl -fsS -o /dev/null -w 'Gateway HTTP %{http_code}\n' http://127.0.0.1:3000
docker ps -a --filter label=com.docker.compose.project=property-rescue-switch --format '{{.Names}}: {{.Status}}'
git check-ignore .local/switch/.env .venv .env .local/python .uv-cache
git diff --check
```

- Locked sync: exit 0, one virtual project resolved, no external packages installed.
- Final tests: **12 tests, 0 failures/errors/skips, 0.542 seconds, OK**, exit 0.
  Fixtures/local HTTP only, no real agent communication in these tests.
- Earlier sandbox test run: 11 passed, one errored because loopback socket binding
  was denied. Reran with permitted loopback access. First successful run exposed
  ResourceWarnings; closed HTTPError objects and reran with ResourceWarning errors.
- Initial network/Docker checks were sandbox-denied; escalated retries succeeded.
  Initial old-uv run exited 2 (interpreter unavailable); new uv resolved it.
- Preparation and Compose startup: exit 0. `init-db` and `setup` exited 0;
  Switch and Gateway running; Mattermost and provider Postgres healthy.
- Health: Switch `status=ok`, Mattermost `status=OK`, Gateway HTTP 200.
- Ignore checks: all five local credential/runtime paths ignored. `git diff --check`
  exited 0 (limited to tracked diff; files are still untracked).
- An in-memory scan of all **16 nonignored project files** found **0 matches** for
  generated secret values. Tracked-file count is 0. A separate in-memory scan of
  all provider container logs found **0 matches** for generated secret values.
  This checks known local secrets, not a guarantee against every possible secret.
  Application tests also assert token/body redaction. No raw provider logs saved.

### Real service evidence — not a completed agent proof

Using documented bootstrap paths with credentials loaded locally (never printed):

- `POST /gateway/auth/login`: HTTP 200; authenticated
  `GET /gateway/collaborations` returned default Mattermost bridge
  **89a03e00-d90a-4d15-be08-70f2f0253dc5**, status **active**.
- `POST /api/v4/users/login`: HTTP 200 for seeded human account `user`, ID
  **y7iu8dci53djxpg1xwmydzaa8h**. Response/session token not logged or saved.
- Official setup logs contained its completion marker. The service checks were
  performed by a one-off standard-library Python probe against actual containers.
- No proof room, live agent session, run UUID, human post, agent reply or targeted
  handoff has yet been observed. No message IDs are fabricated. The transcript
  verifier deliberately cannot certify Switch runtime provenance by itself.

### Blockers and next action

The user confirmed they will perform the interactive setup. Install Console
0.40.1, authenticate a provider, connect to this existing local server, apply
`connectivity.template.yaml`, and send the human kickoff in Mattermost. Follow
README.md's manual steps, fill the ignored proof environment locally, then run
the transcript check and capture matching Switch session/tool-call identifiers.
No secrets should be pasted into chat.

Still unverified: template execution, agent provider availability, exact live
thread mapping, runtime duplicate/reconnect behavior, human-agent round trip and
agent-agent exchange. The existing automated checks and healthy services do not
satisfy these acceptance criteria. Stack left running for the user's setup;
README.md includes a non-destructive stop command. Stop at Checkpoint 1; do not
begin Checkpoint 2 without further approval.


## Live transcript follow-up — 2026-11-04

The user connected Console, reported Codex signed in, imported the template,
created the room and agents, and sent the human kickoff. A read-only live probe
loaded existing local Mattermost credentials, logged in without printing the
session token, and invoked `Settings.from_env` and `proof.verify` with the real
`MattermostReader`. Result: `mattermost_transcript_verified`.

- Run: `6d926bba-40fd-4a6d-a580-cf3207fd0a19`.
- Channel: `wobz6wqew3nqjk9jcc9ohme6ty`.
- Root: `rcpxzyfsztf3bp8g863k8mnath`.
- Human user ID: `y7iu8dci53djxpg1xwmydzaa8h`.
- Coordinator bot ID: `tendkrhzxigzt8q5tsm1q17qnr`.
- Worker bot ID: `akw5en64bif8xgeinxsnwygq5o`.

| Stage | Mattermost post ID | Server timestamp (epoch ms) |
| --- | --- | --- |
| PR_CONNECT | rcpxzyfsztf3bp8g863k8mnath | 1793793528992 |
| PR_ACK | asbc89a5zf8g5ds7uuya6s144y | 1793793546169 |
| PR_TASK | re9qf6thabrzjr1oopi3e4c8ur | 1793793549915 |
| PR_RESULT | 94wrcxcbs3bbfxo47cibipza6e | 1793793563346 |
| PR_DONE | is4cksdesjbibegcyx95fkgk7c | 1793793570248 |

All five stages passed checks for correct sender, same thread/channel, run UUID,
recipient mentions, chronological order and absence of edited/deleted or duplicate
stages. These are real API results, not fixture data. The verifier still reports
`switch_runtime_verified: false`, intentionally: matching Console runtime/tool-call
records are needed to establish the Switch delivery path.

A read-only query of Console's local `messages` table for this run UUID returned
no rows; this does not establish that runtime records are unavailable elsewhere.
Next action: inspect the coordinator and worker sessions in Console and capture
matching received-message and targeted-message tool results, with room/session IDs.
Only PROGRESS.md changed in this follow-up; no application changes or new test run.
Checkpoint 1 is not yet marked complete; no work on Checkpoint 2.


## Checkpoint 1 completion — 2026-11-04

Evidence combines the API-verified transcript above with manual runtime activity
inspection in that same thread. The user supplied Switch-generated “Show activity”
reports, not an agent's own assertion that it used a tool:

- Coordinator: 20 seconds, four successful tool calls: `switch.connect_to_room`,
  `switch.read_context`, `switch.post_message`, `switch.send_targeted_message`.
  User-visible activity report IDs: `m4wipk67hin1upqhccpjobebeo` and
  `ge47t894dibrzxytcq3wa3y4ka` (two views of the same activity, not two handoffs).
- Worker: 12 seconds, three successful calls: `switch.connect_to_room`,
  `switch.read_context`, `switch.send_targeted_message`.
  User-visible activity report ID: `gnudas3akidg7ni6fyz5ychmar`, read at
  12:07:30 UTC as reported by the UI.
- The activity reports are ephemeral (“Only visible to you”). Their IDs are
  recorded for provenance, not promised to be retrievable permanent evidence.
  They were provided by the user; they were not independently fetched by this
  assistant. Full tool arguments and internal Switch session IDs were not captured.

Together with the recorded real human/bot identities, run UUID, ordered targeted
messages and thread/post IDs, these reports establish the intended Switch path
for this limited connectivity demonstration. All Checkpoint 1 acceptance criteria
have supporting evidence. There are no remaining blockers to this proof.
The transcript checker correctly continues to return `switch_runtime_verified:
false`: it cannot automate the additional manual activity check.

Final automated command:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked python -W error::ResourceWarning -m unittest discover -s tests -v
```

Result: **12 tests passed, 0 failures/errors/skips, 0.585 seconds**, exit 0.
The initial sandbox run had one loopback-binding PermissionError (11 other tests
passed); the same command succeeded with permitted loopback access. These remain
offline fixture/local HTTP tests, separate from the live evidence.

Changed files in this completion update: PROGRESS.md and README.md only. README
now reflects the observed single Server address field and the working browser
Mattermost URL. No application code or dependencies changed. Prior known-secret
scan and ignore checks remain recorded above; no credentials added to this update.

Limits: no forced disconnect/replay or durable exactly-once guarantee was tested;
no maintenance authorization/execution behavior is claimed. An incorrect internal
Mattermost browser link was observed; use http://localhost:8065 instead. This does
not prevent the demonstrated message exchange. Later integration work should
correct the bridge public URL. Next action: user review and explicit approval
before starting Checkpoint 2. No Checkpoint 2 work performed.


## Checkpoint 2 completion — 2026-11-04

### Delivered behavior and decisions

- Added a separate application PostgreSQL 18.6 instance on loopback port 55432;
  Switch's provider database and integrations were not changed.
- Added typed SQLAlchemy models for users, credential hashes, teams, memberships,
  properties, tenancies, requests, incidents, maintenance history, warranties and
  property-scoped vendors. Foreign keys and checks enforce owner/tenant roles,
  property boundaries and a human team coordinator for each incident.
- Added explicit Alembic migration `21697e9b513b`. No automatic schema changes
  occur on API startup. Migration down/up is tested only in disposable test schemas.
- Implemented thin FastAPI routes over service-layer authorization and business
  operations. Tenants submit requests only for active tenancies and read only
  their own requests. Owners read their properties' records; assigned team staff
  read their team's managed properties. Owners and coordinators can acknowledge;
  ordinary team members cannot. Unrelated resource IDs return 404.
- Requests start submitted and can transition only to acknowledged in this
  checkpoint. Repeated acknowledgement is idempotent. A PostgreSQL trigger also
  rejects reverse transitions and rewrites to original complaint fields, identity,
  property, timestamps or idempotency key. No closure or consequential action API.
- UUID idempotency keys are unique per tenant. A matching retry returns the same
  record; a changed payload under the same key returns 409. Four concurrent
  submissions were tested to commit exactly one record.
- Fictional fixtures use deterministic UUIDs and can be seeded repeatedly without
  duplicate rows or resetting existing states. Eight demo users, one team, two
  memberships, three properties, four tenancies, four requests, one incident,
  and three each of histories, warranties and vendors are seeded. Two original
  requests remain distinct while referencing the same incident. Incident linking
  UI/workflows remain Checkpoint 5 work; the model and read endpoint exist now.
- Authentication decision: randomly generated local demo bearer tokens, stored
  privately once and hashed in PostgreSQL. Identity and roles are loaded from the
  database on every request; client-provided role/user fields cannot authorize.
  Revoked tokens and inactive users are denied. No login/SSO/signup service added.
- No React, agent investigation, approval execution, vendor communication,
  scheduling or spending features were implemented. Switch communication was
  not re-demonstrated in this checkpoint; its previous evidence is retained.

### Files created or changed

Created:

- `compose.yaml`: isolated application database, loopback binding, persistent volume.
- `scripts/prepare_app.py`: generate private application configuration, no overwrite.
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`,
  `migrations/versions/21697e9b513b_core_maintenance_records.py`: schema management.
- `property_rescue/database.py`, `models.py`, `schemas.py`, `service.py`, `api.py`,
  `seed.py`: configuration, persistence, contracts, business logic, routes and seeds.
- `tests/test_maintenance.py`: configuration and real PostgreSQL/API integration tests.

Changed:

- `pyproject.toml`, `uv.lock`: project version 0.2.0 and reproducible dependencies.
- `.env.example`: placeholder-only application configuration notes.
- `property_rescue/__init__.py`: package description.
- `README.md`: short API walkthrough first, then reproduction, roles, endpoints,
  sources and compatibility decisions; previous connectivity guide retained.
- `PROGRESS.md`: this checkpoint report and status.

Generated ignored artifacts: `.local/app/.env` and `.local/app/demo-tokens.json`,
both mode 0600. The temporary Alembic-generated generic README was removed; it
contained no project-specific instructions. AGENTS.md, PLAN.md and existing
connectivity code/tests/template were preserved. No Git commit or staging done;
all project files were still untracked at this checkpoint.

### Dependency verification

Before installation, queried official PyPI JSON metadata for FastAPI, SQLAlchemy,
Psycopg, Alembic, Uvicorn and the test client. Consulted official SQLAlchemy
psycopg dialect, Alembic migration, FastAPI security, Psycopg supported-platform,
PostgreSQL release-policy and Docker official-image documentation. Full URLs and
constraints are in README.md.

Selected direct pins:

| Dependency | Version |
| --- | --- |
| FastAPI | 0.162.0 |
| SQLAlchemy | 2.1.8 |
| Psycopg / psycopg-binary | 3.3.8 |
| Pydantic | 2.14.2 |
| Alembic | 1.20.1 |
| Uvicorn | 0.54.0 |
| HTTPX2 (development tests only) | 2.16.0 |

Python remains 3.15.2 and uv remains 0.13.7. Metadata accepts the interpreter and
SQLAlchemy/Psycopg/Alembic combination; installation, imports, dependency checking
and the real PostgreSQL suite verify it in use. Transitive pins include Starlette
1.10.0 and pydantic-core 2.50.2; all are in uv.lock. Direct Pydantic usage is
explicitly declared rather than relying only on FastAPI's transitive requirement.

Initial HTTPX 0.28.1 tests passed but emitted Starlette's deprecation warning.
Inspected installed Starlette's supported client selection and official HTTPX2
metadata, then replaced HTTPX with HTTPX2 2.16.0. Final tests have no such warning.
No optional FastAPI/Uvicorn extras, lint framework or separate test framework added.

Application database image: `postgres:18.6-alpine`, verified stable rather than the
available PostgreSQL 19 release candidate. Pulled digest:
`postgres@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5`.

### Exact commands and results

Commands run from the project root (uv executable already installed locally):

```sh
.venv/bin/python scripts/prepare_app.py
docker compose --env-file .local/app/.env up -d --wait
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --env-file .local/app/.env alembic revision --autogenerate -m 'core maintenance records'
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --env-file .local/app/.env alembic upgrade head
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -m property_rescue.seed
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -W error::ResourceWarning -m unittest discover -s tests -v
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic check
UV_CACHE_DIR=.uv-cache .local/uv-aarch64-apple-darwin/uv pip check
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv sync --locked
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic current
```

All final commands exited 0. The generated migration was reviewed and augmented
with the immutable-original/state-transition trigger before applying it.

- First full suite: **30 passed in 4.310s**, with the HTTPX deprecation warning.
- Final suite after replacing the client: **30 passed in 5.237s**, zero failures,
  errors or skips. 12 connectivity tests, one application configuration test,
  17 real PostgreSQL integration tests. Network/loopback permission was granted.
- PostgreSQL tests create random isolated schemas, apply migrations, seed fixtures,
  exercise APIs/constraints and drop only those owned schemas. No SQLite or fake
  persistence is substituted. Real agent integrations are not exercised by these tests.
- `alembic check`: **No new upgrade operations detected.**
- `alembic current`: **21697e9b513b (head)**.
- `uv pip check`: **23 packages checked; all installed packages compatible**.
- `uv sync --locked`: **26 packages resolved, 23 checked**, no lockfile changes needed.
- Docker service `property-rescue-app-db-1`: healthy, listening on 127.0.0.1:55432.
- `git diff --check`: exit 0 (limited for untracked files).

### Live HTTP evidence

Started the real ASGI server with:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env uvicorn property_rescue.api:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

A one-off standard-library HTTP probe read demo tokens privately and verified:

| Operation | Observed result |
| --- | --- |
| Authenticated tenant `/me` and `/properties` | HTTP 200 |
| POST fictional complaint with a fresh stable smoke-test key | HTTP 201 |
| Repeat identical request/key | HTTP 200, same request ID |
| Owner GET of the new request | HTTP 200 |
| Unrelated owner GET | HTTP 404 |
| Unauthenticated GET /requests | HTTP 401 |
| Owner property history | HTTP 200, one fictional prior repair |

Persisted smoke request ID: `3e726752-fb77-43b3-a487-ab5ef2555a4b`. It remains as a
fifth fictional demo request; rerunning the normal seed does not remove it.
The test suite separately verified retrieval from a newly created application
instance using the same PostgreSQL data.

### Secret handling and practical limits

- In-memory scan of **29 nonignored project files** found **0 files matching known
  generated Switch/application credentials or any local demo token**. Credentials
  were never printed. `git check-ignore` confirms both application secret files
  are ignored; permissions verified as 0600.
- In-memory application database container log scan found **0 known application
  secret values**. API access logging is disabled; observed server startup logs
  contain only process/server status. Automated failure tests check sanitized
  database errors and validation responses. These are known-secret checks, not
  a claim of exhaustive secret detection.
- Local demo authentication and database administration credentials are for this
  development environment. No production identity lifecycle, least-privilege
  runtime DB role, production hosting or security deployment is claimed.
- No remaining blockers for Checkpoint 2 acceptance. Runtime agent investigation,
  consequential approvals, incident coordination UI and frontend remain future work.
- API and application database left running for review. README begins with a
  short `/docs` walkthrough, including how to authorize locally and submit a request.

Next action: user review of Checkpoint 2 and explicit authorization for Checkpoint 3.
Do not begin Checkpoint 3 automatically.


## Checkpoint 3 implementation report — 2026-11-06

### Delivered and verified

- Read AGENTS.md, PLAN.md and current progress; rechecked the official pinned
  Console 0.40.1 template language and agent protocol before coding integration.
  Verified private channel type, owner/agent addressing, permission-bypass and
  agent-management fields. Retained official Console runtimes and targeted
  messages; did not build against Switch's experimental task-event API.
- Added deterministic database evidence collectors for triage, history/similar
  complaints/warranties, and vendor/estimate context. These are replaceable
  `EvidenceTool` integrations, not simulated LLM agents. Actual AI reasoning is
  assigned to `pr-triage`, `pr-history` and `pr-vendors` in Switch Console.
- Persisted investigation runs, dated evidence snapshots, per-step outcomes,
  source citations and ordered activity. Same creation key returns the same run;
  failed sections retry selectively under a new retry key. Repeating a retry key
  cannot rerun a failed attempt. SQL savepoints isolate tool errors. Provider
  exceptions are sanitized instead of storing response bodies or credentials.
- Authorization applies before start and on every read/retry/export. Only the
  request's owner or assigned team staff can collect/export management evidence.
  Tenants and unrelated accounts are denied. Same-category comparisons are
  restricted to the same property, not other owners' requests.
- Added three fictional planning allowances, linked to property/vendor/category,
  with explicit assumptions, currency, bounds and validity dates. Demo plumbing
  range USD 150–300 is not a quote or authorization. Outdated/unmatched allowances
  produce missing-estimate findings. Historical repair costs are not extrapolated.
- Complaint category is tenant-reported, urgency/cause unverified, warranty date
  validity does not establish asset match/coverage, and vendor availability and
  qualifications remain unverified. Proposals are suggestions for human review,
  with no repair execution, spending, vendor contact, scheduling or closure API.
- Prepared private Switch template using shared room context only: no application
  token, database credentials, external connections or agent-management capability
  is supplied. Permission bypass stays false. Prompt restrictions are not claimed
  to be a hard provider sandbox; unexpected non-messaging tool requests must not
  be approved.
- Reviewed/applied additive migration `84836fd49c2c`, seeded allowances, restarted
  only the verified application API process on port 8100, and verified a real
  evidence-collection HTTP request. Existing records were preserved. New fixtures
  use a fixed fictional complaint timestamp for reproducible historical tests.

### Files created or changed

Created:

- `property_rescue/investigation.py`: typed evidence contracts, real database
  collectors, authorization, orchestration, retry semantics and Switch briefing.
- `investigation.template.yaml`: three specialist agents and private room.
- `migrations/versions/84836fd49c2c_investigation_evidence_and_planning_.py`.
- `tests/test_investigation.py`: 11 real PostgreSQL evidence/API tests, with
  explicitly injected failure/invalid-result doubles where required.

Changed:

- `property_rescue/models.py`: PlanningEstimate and Investigation persistence.
- `property_rescue/api.py`: start, get, retry and plain-text briefing endpoints;
  injectable evidence tools for verification.
- `property_rescue/seed.py`: fictional allowances and fixed timestamp for new seed
  complaints; existing rows are not overwritten.
- `tests/test_maintenance.py`: extracted reusable PostgreSQL fixture base without
  duplicating the existing tests.
- `README.md`, `PROGRESS.md`: workflow, contracts, evidence, limitations and status.

Generated ignored local file: `.local/app/investigation-brief.txt` (mode 0600), an
8,151-character fictional evidence packet with the run UUID and no credentials.
AGENTS.md, PLAN.md and Checkpoint 1 connectivity code/template remain unchanged.
No new dependencies were installed; existing lockfile and verified pins retained.

### Automated checks

Exact final command:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -W error::ResourceWarning -m unittest discover -s tests -v
```

Result: **41 tests passed in 8.866 seconds**, zero failures/errors/skips, exit 0.
An earlier 40-test suite passed in 7.250 seconds; final changes fixed the test
clock/fictional seed timestamp and added an untrusted-record regression case.

New coverage: property/role boundaries across all endpoints, citation provenance,
current/expired estimates, missing history/warranty evidence, three concurrent
starts with one key, selective retries, duplicate failed-retry keys, SQL-error
savepoint recovery, invalid citations/cross-property evidence rejection, sanitized
failure bodies, credential-free exports and instruction-like record text retained
as data rather than promoted into a proposal. Default collectors leave original
requests and their states untouched. These tests use actual PostgreSQL plus test
clients; they are not live Switch/LLM evidence. All earlier tests still pass.

Other commands/results:

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic revision --autogenerate -m 'investigation evidence and planning allowances'
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic upgrade head
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -m property_rescue.seed
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic check
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic current
UV_CACHE_DIR=.uv-cache .local/uv-aarch64-apple-darwin/uv pip check
```

All exited 0. Migration check: no new upgrade operations detected; revision
84836fd49c2c at head. Dependency check: 23 packages compatible. Known-secret scan
of 33 nonignored files plus the exported briefing found zero local generated
credential/token matches. `git diff --check` passed (limited for untracked files).
Docker/ps reads initially blocked by sandbox permissions succeeded on authorized
retry. No application test failures occurred in this checkpoint.

### Live service evidence and outstanding agent check

- Real HTTP-created investigation: `e0ecd9c3-a72f-4cae-84e7-144c39d000dc` for the
  seeded `water_request_one` complaint. All three evidence sections succeeded;
  status `ready_for_review`, `agent_review=not_verified`. The plain-text brief
  was fetched via the authenticated API and saved locally for the human to send.
- The user reported creating the investigation room. Authenticated Mattermost
  read confirmed channel `f1ziwb4ajpyg8ghyam3c18xugh`, type **P (private)**.
- The user reported an unreachable browser link. Actual Mattermost ping returned
  `status=OK`; localhost investigation room page returned HTTP 200. Using the
  official setup contract, patched the existing bridge's `connection_config.public_url`
  to `http://localhost:8065`; server returned HTTP 200. Internal bridge URL and
  credentials were not changed. New generated-link behavior still needs UI confirmation.
- Read of the new room had no messages containing the investigation run UUID at
  the time checked. No specialist findings, final report or agent tool results
  for this investigation have been observed yet. No messages were posted by this
  assistant on the user's behalf.

### Limits, blocker and next step

Backend collection is synchronous; activity becomes readable after commit, not a
streamed owner timeline (Checkpoint 4). Snapshot sections retain their own dates;
retry refreshes only failed steps. Missing records can still produce a successful
collection with explicitly missing findings. Agent review remains in Switch;
there is no automatic ingestion or machine certification of LLM conclusions.
Manual history-based agent retries are not a durable exactly-once mechanism or an
automatic timeout supervisor. No consequential action execution exists.

Live Checkpoint 3 acceptance remains blocked on the human sending the prepared
brief in the created room and the actual three-agent exchange. The user has been
given the working localhost URL and the credential-free local file to paste.
Next: observe INV_ACK, both specialist tasks/results and INV_REPORT in one thread;
validate citations/uncertainty and inspect actual Switch activities. Record root,
post and sender IDs and observed results before marking Checkpoint 3 complete.
Do not proceed to Checkpoint 4 without explicit authorization.


## Checkpoint 3 live agent verification — 2026-11-06

The user posted `.local/app/investigation-brief.txt` as the human kickoff in the
private room. A read-only probe logged in as the human Mattermost account (token
never printed or saved) and read every post in the channel via
`GET /api/v4/channels/{id}` and `GET /api/v4/channels/{id}/posts`. No messages
were posted by this assistant.

- Channel: `f1ziwb4ajpyg8ghyam3c18xugh`, type **P**, `property-rescue-investigation`.
- Root (INV_START): `yi9dk648tt8cixsg6b7u4mbrhr`, by human `user`
  (`y7iu8dci53djxpg1xwmydzaa8h`, not a bot). Its content equals the exported brief.
- Bots: pr-triage `888zezatpidkzrdg619keez43o`, pr-history
  `psbxs9at17rd7d6odwnt6hmqkr`, pr-vendors `c5qkmihomprhbdtb6oz4mi6czc`.

| Stage | Sender | Post ID | Server time (epoch ms) |
| --- | --- | --- | --- |
| INV_START | user | yi9dk648tt8cixsg6b7u4mbrhr | 1793999622217 |
| INV_ACK | pr-triage | 75qe9zd6k7bi7g1fz1ikru836w | 1793999648079 |
| INV_HISTORY_TASK | pr-triage → pr-history | 67owcd5j1tyqifsiq3muubj85c | 1793999648225 |
| INV_VENDOR_TASK | pr-triage → pr-vendors | tmhk1iuc67rk8df8ces48hqy6e | 1793999648797 |
| INV_VENDOR_RESULT | pr-vendors → pr-triage | ecbqo7bdm3ggdghzk4gqc75w4o | 1793999671156 |
| INV_HISTORY_RESULT | pr-history → pr-triage | yudzsn1zj3n8b8j9zf1sp6w59w | 1793999671759 |
| INV_REPORT | pr-triage | jr179rd9fp8mub99oo398eas3e | 1793999699967 |

Checks performed on the actual posts:

- All stages are in the root's thread, chronologically ordered, from the expected
  senders, each containing the run UUID. Each stage appears exactly once; no
  INV_BLOCKED or *_FAILED messages. Stage posts are unedited and undeleted; only
  Switch's "Worked for…" status posts are edited, as the runtime updates them.
- Citations: history result cites 4 source IDs, vendor result 3, final report 6;
  **all exist in the packet** (zero unknown IDs). Amounts in the report (185.00,
  150.00, 300.00) all appear in the packet.
- Report content (reviewed manually): separates facts, hypotheses, missing data
  and proposals; labels the historical cost as not an estimate; keeps warranty
  `coverage_confirmed=false`; states vendor availability is unverified; describes
  the USD 150–300 allowance as not a quote/budget; ends with "No external actions
  taken. Human review required." No vendor contact, scheduling, spending,
  approval or closure occurred; no such tools or APIs exist.

Switch runtime provenance: the user supplied pr-triage's Switch "Show activity"
reports: 5 successful calls (`switch.connect_to_room`, `switch.read_context`,
`switch.post_message`, two `switch.send_targeted_message`), then 1
`switch.post_message` for the interim note and 1 for INV_REPORT. Thread status
posts record pr-history and pr-vendors each completing 3 tool calls. Specialist
per-call activity detail was not supplied. These reports are ephemeral and were
not independently fetched by this assistant.

Observations and limits:

- The user's pasted activity list repeats identical reports with later "Read at"
  times. The channel contains only one of each stage post, so these are repeated
  views, not duplicate executions.
- Race: pr-triage's interim "waiting for history" post
  (`km6r8xb78bdcdgg1np7czc1j3a`) landed ~4.6 s after the history result had
  already arrived. It is stale but harmless; the report followed with both results.
- Agent conclusions are not ingested back into the application database; the
  investigation record keeps `agent_review=not_verified`. Automatic ingestion
  and the live owner timeline belong to Checkpoint 4.
- Failure/retry paths (INV_BLOCKED, INV_RETRY) were not exercised live; they are
  covered for backend collection by automated tests only.

Final automated command (same as above): **41 tests passed in 7.456 s**, zero
failures/errors/skips. `alembic current`: `84836fd49c2c (head)`.
Changed in this update: PROGRESS.md and README.md only.

Next action: user review of Checkpoint 3 and explicit authorization for
Checkpoint 4. Do not begin Checkpoint 4 automatically.


## Checkpoint 4 report — 2026-11-06

### Delivered

- **Actions** (`property_rescue/actions.py`): `contact_vendor`, `schedule_visit`,
  `authorize_spend`, `close_request`. Each is proposed against a completed
  (`ready_for_review`) investigation of the same request and cites evidence IDs
  that must exist in it. Vendors must be in the property's directory. Typed,
  strict payloads (timezone-aware ≤12 h windows, USD amounts 0–100,000). Proposal
  creation is idempotent per request + key; a changed payload under a used key is 409.
- **Policy** (decision recorded here; was an open decision): owner approves and
  executes everything on owned properties; team coordinators approve/execute
  vendor contact, scheduling and closure on team properties; spending is
  owner-only; team members may propose only. Tenants and unrelated accounts are
  refused (403/404). Revisit spending limits for teams in Checkpoint 5.
- **Approval binding**: an immutable decision row records actor, authority,
  revision and a database-computed SHA-256 over details, rationale and evidence;
  approvals expire after 24 h. Clients must echo the revision and hash they
  reviewed. Revising (with `expected_revision`) increments the revision, returns
  to `proposed` and logs `action.approval_invalidated`.
- **Execution boundary**: rechecks executor authority, request not closed,
  approval for the current revision/hash, expiry and the approver's *current*
  authority (deactivated approver blocks execution). Idempotency key: the same
  key (including an earlier failed attempt's) returns the recorded outcome and
  never re-executes; another key after success is 409. Row locks serialize
  concurrent attempts. Failures store only a sanitized code and can be retried
  with a new key while the approval is valid.
- **Database enforcement** (migration `c125b75b4fcf`): triggers refuse
  `executing` without a matching unexpired approval, `approved`/`rejected`
  without a matching decision, illegal transitions, detail changes without a new
  revision, any update/delete of decisions or timeline rows, and closing a
  request unless an approved `close_request` is executing. Request status adds
  `closed`; original complaint fields remain immutable.
- **Owner timeline**: append-only `timeline_events` with a gapless per-request
  sequence (request row lock). Request submission/acknowledgement, investigation
  steps, proposals, decisions, invalidations, denials, execution start/result/
  failure and closure are recorded. `GET …/timeline?after=N` and Server-Sent
  Events stream (`…/timeline/stream`, FastAPI's built-in SSE, re-authenticates
  every poll, resumes via `Last-Event-ID`). Managers only.
- **Executor**: `FictionalDemoExecutor` is the default and is explicitly labelled
  `mode: fictional_demo, delivery: not_sent`; nothing is sent. Closure is a real
  internal transition. Tests inject `RecordingExecutor`, an explicit test double.

### Defects found and fixed during verification

- A trigger precedence bug (`NOT a OR b`) made legitimate closure fail; caught by
  the closure test, fixed with parentheses. The action correctly ended `failed`
  with a sanitized error rather than a false success.
- Stress-running the concurrency test exposed a real deadlock (1 in 20 runs):
  inconsistent request/action lock order combined with foreign-key share locks.
  Fixed with one rule — writers lock the request row first (`service.lock_request`),
  applied to actions, proposals, investigation retries and timeline writes.
  After the fix: **0 failures in 30 repeated runs** of the action and concurrency tests.

### Files

Created: `property_rescue/actions.py`, `tests/test_actions.py` (11 tests),
`migrations/versions/c125b75b4fcf_approval_enforced_actions_and_timeline.py`,
`scripts/demo_owner_workflow.py` (live scenario checker; stdlib only).

Changed: `models.py` (actions, decisions, timeline, `closed` state, named
investigation/request unique key), `service.py` (`lock_request`, `record_event`,
events on submit/acknowledge), `investigation.py` (timeline events, lock order),
`api.py` (action, timeline and SSE routes; injectable executor), `README.md`,
`PROGRESS.md`. No dependencies added; lockfile unchanged.

### Exact commands and results

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -W error::ResourceWarning -m unittest discover -s tests -v
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic upgrade head
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic check
UV_CACHE_DIR=.uv-cache .local/uv-aarch64-apple-darwin/uv pip check
.venv/bin/python scripts/demo_owner_workflow.py http://127.0.0.1:8101
```

- Suite: **52 tests passed, 0 failures/errors/skips** (13.8 s); includes the
  existing migration down/up round-trip and model/schema comparison.
- `alembic check`: no new operations; `alembic current`: `c125b75b4fcf (head)`
  on the real application database. `uv pip check`: all compatible.
- Live HTTP scenario: **19/19 checks passed** — request `e65318b6-44d0-464a-9b31-6a925fabddc2`,
  26 timeline events, contact action executed once (fictional delivery), stale and
  replayed attempts refused and logged, closure executed and visible to the tenant.
  Live SSE read with `Last-Event-ID: 23` returned exactly events 24–26.
- Known-secret scan of 37 nonignored files: zero credential/token matches (one
  hit was the non-secret localhost `FRONTEND_BASE_URL`). `git diff --check` exit 0.

### Limits and blockers

- The old background API on port 8100 (PID 62881) could not be stopped from this
  session, so initial live verification used port 8101. The user then stopped it
  and restarted 8100 with the new code; their own run of
  `scripts/demo_owner_workflow.py` passed **19/19 checks** (request
  `b18919f2-db74-4cef-ba2b-2216fd248c7a`, 26 timeline events). The temporary 8101
  server was stopped. The script now refuses to run against an API lacking
  Checkpoint 4 routes instead of failing mid-way.
- No real vendor, calendar or payment integration; agents do not propose actions
  through the API (no agent credentials) — humans create proposals from INV_REPORT.
- Denials are logged only for actors who can see the request (owner/team);
  unrelated or tenant attempts are refused but not written to the owner timeline.
- An action stuck in `executing` after a crash needs manual reconciliation.
- Team incident grouping, team dashboard and Mattermost posting of timeline
  events are Checkpoint 5.

Next action: user review of Checkpoint 4 and explicit authorization for Checkpoint 5.


## Checkpoint 5 report — 2026-11-06

### Delivered

- **Shared queue** (`GET /queue`): managers see each original request with
  property, tenant, incident and coordinator, latest evidence status and action
  counts; status filter. Tenants are refused; unrelated staff see nothing.
- **Incidents** (`property_rescue/incidents.py`): create from several requests
  with a coordinator (idempotent per property + key), link/unlink (idempotent),
  reassign coordinator. Owner and team coordinators only; members 403. Requests
  must share the incident's property, be open and not linked elsewhere. Original
  complaints are untouched (database trigger from Checkpoint 2). Every change is
  on each affected request's timeline. Lock order: request rows (sorted) then incident.
- **Team policy** (decisions recorded here): for a request in an incident only
  that incident's coordinator holds coordinator authority; coordinators may
  approve/execute spending up to `teams.coordinator_spend_limit` (seeded USD 500,
  NULL = owner-only). Reassignment makes the previous coordinator's unexecuted
  approvals fail with `approver_lost_authority`. Seed adds coordinator Riley
  (`coordinator_two`); the token file gains her token without changing others.
- **Mattermost link** (`property_rescue/collaboration.py`): sync finds the human
  (non-bot) `INV_START <run>` root post in the investigation channel, reads its
  thread, imports posts mentioning the run (deleted posts and Switch status posts
  skipped), stores sender, bot flag, leading INV_* tag, text and post ID
  (idempotent by post ID), and records `collaboration.message` timeline events.
  `agent_review` becomes `in_discussion` / `report_received` / `blocked` — an
  arrival state, not certification. Not configured → 503; Mattermost errors →
  502 with the reader's sanitized message. GET-only reader; config validation is
  shared with the Checkpoint 1 proof.
- **Dashboard** (`frontend/`): token sign-in (sessionStorage), tenant view
  (report + own requests), manager view (queue, incident grouping/reassign/unlink,
  request detail with evidence findings and sources, copy brief, sync agent
  discussion, propose/approve/reject/execute with backend refusals shown, live
  timeline over fetch-based SSE with resume). Vite proxies `/api` to 8100.

### Defects found during this checkpoint

- Route function `incidents` inside `create_app` shadowed the new module (10
  test errors); renamed to `property_incidents`.
- The Checkpoint 4 test asserting coordinators cannot approve USD 220 became
  wrong under the new team limit; now tests both sides (220 allowed, 750 refused).
- Frontend tests passed on first run, so two deliberate mutations were applied
  (wrong revision sent; refused execution reported as success): both were caught
  (2 failures), then reverted (11/11 pass).

### Files

Created: `property_rescue/incidents.py`, `property_rescue/collaboration.py`,
`migrations/versions/c6df82f576bf_team_incidents_and_collaboration.py`,
`tests/test_team.py` (7 tests; `FakeMattermost` is an explicit test double),
`scripts/demo_team_workflow.py`, `scripts/connect_mattermost.py`, and
`frontend/` (package.json, package-lock.json, tsconfig.json, vite.config.ts,
index.html, .gitignore, src/: api.ts, types.ts, App.tsx, ManagerView.tsx,
TenantView.tsx, RequestDetail.tsx, Actions.tsx, styles.css, main.tsx,
vite-env.d.ts, testing.ts, test-setup.ts and three test files).

Changed: `models.py` (team spend limit, incident key, collaboration messages),
`actions.py` (`authority` incident-aware, `permitted` replaces static table),
`api.py` (queue/incident/staff/collaboration routes, injectable Mattermost),
`investigation.py` (listing, agent-review state), `config.py` (shared Mattermost
origin/token validation), `messaging.py` (`user_by_id`, `channel_posts`),
`seed.py` (Riley, spend limit, token-file top-up), `tests/test_actions.py`
(`ActionCase` base; spend-limit test), `README.md`, `PROGRESS.md`.

### Dependency verification

Queried npm registry metadata (engines, peer dependencies) and the official
Node release index on 2026-11-06. Selected exact pins: react/react-dom 19.3.1,
typescript 7.0.2, vite 8.3.6, @vitejs/plugin-react 6.2.1 (peer vite ^8),
vitest 5.1.0 (peer vite ^6–8, node ≥26 ok), jsdom 31.0.0 (node ≥26 ok),
@testing-library/react 16.3.3 (peer react ^19, dom ^10), @testing-library/dom
10.4.2, user-event 14.6.8, @types/react(-dom) 19.3.0. jest-dom intentionally not
added. Installed Node 26.5.0 / npm 11.17.0 (Node 26 LTS starts at 26.13.0 —
upgrade recommended). `npm install` added 88 packages; no Python dependencies added.

### Exact commands and results

```sh
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -W error::ResourceWarning -m unittest discover -s tests -v
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic upgrade head
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python -m property_rescue.seed
UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env alembic check
cd frontend && npx tsc --noEmit && npx vitest run && npm run build
.venv/bin/python scripts/demo_team_workflow.py http://127.0.0.1:5173/api
.venv/bin/python scripts/demo_owner_workflow.py
```

- Backend: **59 passed**, 0 failures/errors/skips (~20 s of test time).
  Migration head `c6df82f576bf`; `alembic check` clean; `uv pip check` compatible.
- Frontend: typecheck clean; **11 passed** (SSE parsing, client auth/idempotency
  and refusal surfacing, stream resume/stop, approve binds revision+hash, refused
  execution never shown as success, fictional result labelling, proposal payload
  and validation refusal, tenant view, incident grouping with 409 shown, bad token).
  Production build 241 kB JS (75 kB gzip).
- Live (real API on 8100 + real PostgreSQL, through the Vite proxy): team
  scenario **18/18 PASS**; Mattermost sync reported "not configured" and was not
  counted. Checkpoint 4 owner scenario still **ALL CHECKS PASSED**. SSE through
  the proxy delivered the first of 26 events in 0.01 s (not buffered).
- Known-secret scan: 67 nonignored files plus the built bundle, **0 matches**;
  `node_modules` ignored. `git diff --check` exit 0.
- Environment note: several commands showed multi-minute wall-clock stalls
  outside test execution (e.g. a plain import took >120 s once, then 0.4 s).
  Not reproducible in isolation; test timings themselves were normal.

### Limits and blockers

- **Live Mattermost sync not yet demonstrated.** Storing the Mattermost session
  token was (appropriately) left to the user: run `scripts/connect_mattermost.py`,
  restart the API, open investigation `e0ecd9c3-…` (or post a new brief) and sync.
  Until then only the fake-reader tests cover sync.
- The dashboard was verified by component tests and the live API via its proxy;
  no automated browser run or visual review was performed in this session.
- Dashboard sign-in is local demo bearer tokens, not production auth. Queue
  refreshes every 10 s; request detail is live via SSE.
- Incidents have no resolved/closed state yet; requests close individually via
  approved `close_request`. Agents still do not call the API; humans relay.
- API (8100) and Vite (5173) were started by this session in the background.

Next: user review (dashboard walkthrough + Mattermost sync), then authorization
for Checkpoint 6 (end-to-end tests, demo and submission).


### Checkpoint 5 live Mattermost verification — 2026-11-06

The user ran `scripts/connect_mattermost.py` (configured channel
`f1ziwb4ajpyg8ghyam3c18xugh`), the migration and the seed; their team scenario
run passed 18/18 (sync was skipped because the API had not been restarted).
After restarting the API (the session-owned process on 8100), a real
`POST /investigations/e0ecd9c3-a72f-4cae-84e7-144c39d000dc/collaboration/sync`
as the owner returned HTTP 200 and imported 8 posts from the live Mattermost API:

| Post ID | Sender | Kind | Tag |
| --- | --- | --- | --- |
| yi9dk648tt8cixsg6b7u4mbrhr | user | human | INV_START |
| 75qe9zd6k7bi7g1fz1ikru836w | pr-triage | agent | INV_ACK |
| 67owcd5j1tyqifsiq3muubj85c | pr-triage | agent | INV_HISTORY_TASK |
| tmhk1iuc67rk8df8ces48hqy6e | pr-triage | agent | INV_VENDOR_TASK |
| ecbqo7bdm3ggdghzk4gqc75w4o | pr-vendors | agent | INV_VENDOR_RESULT |
| yudzsn1zj3n8b8j9zf1sp6w59w | pr-history | agent | INV_HISTORY_RESULT |
| km6r8xb78bdcdgg1np7czc1j3a | pr-triage | agent | (interim note, no tag) |
| jr179rd9fp8mub99oo398eas3e | pr-triage | agent | INV_REPORT |

These match the IDs recorded independently in the Checkpoint 3 verification.
Switch "Worked for…" status posts were skipped as designed. A second sync
returned the same 8 messages (no duplicates). `agent_review` became
`report_received`; the request timeline gained 8 `collaboration.message`
events. Tenant sync → 403; unrelated owner → 404. No posts were made to
Mattermost (GET only).

The user's `demo_owner_workflow.py` run failed only because zsh passed the
inline `# comment` as the URL argument (interactive comments disabled). Both
demo scripts now reject non-URL arguments with a usage message.


## Checkpoint 6 report — 2026-11-07 (IST) / 2026-11-06 (EST)

### Hackathon requirements (fetched from the official pages)

Sources: https://www.wemakedevs.org/hackathons/switch and
https://www.wemakedevs.org/hackathons/switch/rules (fetched 2026-11-07 09:45 IST).
Recorded requirements: Switch must be central and the README must show how;
a team-chat workflow where at least one agent and one person complete a real task
through Switch; the Switch setup and agent workflow must be built during the
event; judges assess use of Switch, technical execution ("could someone clone the
repo and reproduce it?"), creativity/impact and presentation (demo video +
README); deadline **Nov 7, 11:59 PM IST**; solo or teams up to 4; AI use permitted
if the entrant understands the work; originality and third-party license
compliance warranted by the entrant. Neither page states a license requirement,
video length or form fields; the track 01/02 definitions are on pages not fetched.

Built-during-event check (file birth times converted to IST): earliest project
file 2026-11-04 08:41 IST (window opened 00:01 IST); Switch stack files 09:20 IST;
investigation template 2026-11-07 02:32 IST; live agent run ≈02:43 IST. All inside.

### Delivered

- `scripts/run_checks.py`: one command running the backend/frontend suites,
  migration check, both end-to-end scenarios, live Switch thread import and
  idempotent re-sync, access refusals, and **real** failure recovery: temporary
  API instances on 8101 with an invalid Mattermost token (real Mattermost
  returned 401 → API 502, no secret echoed) and an unreachable Mattermost URL
  (→ 502 "connection failed"); the healthy API remained correct afterwards.
  Writes `docs/CHECK_RESULTS.md`.
- `README.md`: judge-facing top section (what it is, how Switch is used with a
  flow diagram, modes, clone quick start, honest limits); per-checkpoint guides
  kept below. Fixed the stale "no third-party Python dependencies" statement.
- `DEMO.md`: about 3-minute shot list centred on a live Switch run, with
  preparation and on-camera fallbacks. `SUBMISSION.md`: description, Switch usage,
  verification, limits and a requirement checklist.
- Both demo scripts reject non-URL arguments (zsh inline-comment incident).

### Exact commands and results

```sh
.venv/bin/python scripts/run_checks.py
```

**15/15 PASS** (see `docs/CHECK_RESULTS.md`): 59 backend tests OK; `alembic
check` clean; frontend typecheck, 11 tests and build OK; owner scenario 19 checks;
team scenario 19 checks via the Vite proxy; live import of 8 posts from the three
agents (tags INV_START → INV_ACK → INV_HISTORY_TASK → INV_VENDOR_TASK →
INV_VENDOR_RESULT → INV_HISTORY_RESULT → INV_REPORT); re-sync identical; tenant
403 / other owner 404; both live failure checks 502 without leaks; recovery OK.

Clean-copy reproduction: copied exactly the 66 files git would include (no
`.local`, `.venv`, `node_modules`, `dist`, `.env`) to a scratch directory, then
`uv sync --locked` → 59 tests OK (21.7 s) → `npm ci` → 11 tests passed → build OK.

### Not done / user decisions

- **Demo video** — must be recorded by the user (DEMO.md). Consider a fresh live
  team-mode agent run on camera; only the individual-mode request has a recorded
  live agent thread so far.
- **Publishing** — the project has no commits and no remote; per AGENTS.md nothing
  was committed or pushed. A public repository is needed for judging.
- **License** — none chosen; the rules only require third-party license compliance.
- Agent failure paths (`INV_BLOCKED` / `INV_RETRY`) were not exercised live.


## Post-completion wiring fixes — 2026-11-07

- Changed `property_rescue/messaging.py` to page backward through Mattermost channel
  history using `before` instead of searching only the newest 200 posts. Malformed,
  non-advancing, failed, or over-limit scans fail explicitly, never return partial success.
- Changed `property_rescue/collaboration.py` to refresh edited message text/tags and
  remove retracted or no-longer-correlated posts after successful reads. A removed
  kickoff invalidates its imported discussion. Audit events retain update/removal
  identifiers; withdrawn reports no longer count as `report_received`. Failed reads
  preserve the prior import. Incomplete thread responses are rejected.
- Added four regression tests in `tests/test_connectivity.py` and `tests/test_team.py`
  for old-history discovery, pagination failures, edits/deletions, idempotent resync,
  removal of the kickoff, and preservation on integration failure.
- `scripts/run_checks.py` now requires `--run-id UUID` and reads the investigation as
  owner, supporting both individual and team-property runs. Updated README.md,
  DEMO.md, and SUBMISSION.md. No dependencies or migrations added.
- Protocol reference: official Mattermost API v4 `posts.yaml`, channel-post `before`
  pagination, unpaginated thread reads, and deletion visibility:
  https://github.com/mattermost/mattermost/blob/master/api/v4/source/posts.yaml
- Regression command: `UV_CACHE_DIR=.uv-cache UV_PYTHON_INSTALL_DIR=.local/python
  .local/uv-aarch64-apple-darwin/uv run --locked --env-file .local/app/.env python
  -W error::ResourceWarning -m unittest discover -s tests` — 63 tests OK (29.790 s).
- Restarted the local API on port 8100 with these changes.
- Prepared a NEW fictional request through `http://127.0.0.1:5173/api`:
  `e2e01d4b-879c-426a-a3fb-60fa2bf8c6a0`, title
  “Fresh verification: kitchen tap dripping”. Investigation
  `b66b0ff4-d1fb-48ea-a675-4f3d7bd125f4` is `ready_for_review`.
  Brief is in ignored `.local/app/fresh-investigation-brief.txt`; identifiers are in
  `.local/app/fresh-investigation.json`.
- Fresh LIVE agent verification remains pending: the user must copy the brief from
  the dashboard into the private Switch room with Console running. No browser
  automation tool is available in this session. No new agent run is claimed yet.
- Full command: `.venv/bin/python scripts/run_checks.py --run-id
  e0ecd9c3-a72f-4cae-84e7-144c39d000dc` — **15/15 passed** against the restarted
  API: 63 backend tests (19.764 s), 11 frontend tests, typecheck/build, clean schema
  check, 19 owner and 19 team scenario checks, 8 existing live Mattermost posts,
  duplicate sync, tenant/other-owner refusals, real invalid-token/unreachable
  failures and healthy recovery. `docs/CHECK_RESULTS.md` regenerated. This verifies
  the existing conversation with the new code, not the pending fresh run.
- Next action: after the fresh human post and agent replies, sync investigation
  `b66b0ff4-d1fb-48ea-a675-4f3d7bd125f4` and verify its report and source references.


## Fresh live investigation verified — 2026-11-07

The user's newly posted brief was for **Kitchen tap is dripping**, request
`aecf96c2-05ed-478d-92a0-f43cfdad55c2`, investigation
`3aafb708-fb03-4fcc-a2bb-dfaa460c8edd`. This differs from the separately prepared
`b66b0ff4-d1fb-48ea-a675-4f3d7bd125f4` run, which remains unverified. No evidence
was attached to the wrong request.

- Real human kickoff: `95c3rt9gsiryjj7igp9n4g9h8c` in the private investigation room.
- Real agent sequence: INV_ACK, INV_HISTORY_TASK, INV_VENDOR_TASK,
  INV_VENDOR_RESULT, INV_HISTORY_RESULT, INV_REPORT, with one interim update.
- Final report: `71uambgjhiyriguwighhk5xhuc`, from pr-triage after both specialists.
- Imported 8 posts via the frontend API proxy; owner view is `report_received`.
- Ran `scripts/run_checks.py`'s `live_switch()` against this UUID via `runpy`:
  **5/5 passed** (real import, duplicate sync, linked report, tenant 403,
  unrelated owner 404). No redundant rerun of the already passing full suites.
- Additional assertions: all **16 unique source IDs** cited by agent posts exist
  in this investigation's evidence, and exactly **8 correlated collaboration
  events** exist on this request's timeline. Duplicate sync adds no duplicate posts.
- Reviewed the report against the packet: historical 185.00 cost remains separate
  from the USD 150–300 fictional allowance; warranty dates do not imply coverage;
  vendor availability and diagnosis remain unverified. Findings are proposals,
  not authorizations. No external action was initiated by this verification.
- Evidence snapshots remain ignored under `.local/app/`; non-secret verification
  identifiers are recorded here. Browser clicks were performed by the user;
  this session verified the API/proxy and records, not browser rendering.

Fresh human-to-agents-to-app verification is complete for the actual posted run.
Manual brief posting/sync and fictional vendor/calendar/payment execution remain
intentional limitations. The earlier full suite result remains 15/15, including
63 backend tests and 11 frontend tests.
