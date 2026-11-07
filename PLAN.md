# Property Rescue — implementation plan

## Scope

Deliver a hackathon MVP supporting individual landlords and property management teams. Use a Python/FastAPI modular monolith with PostgreSQL/SQLAlchemy and a React/TypeScript frontend. Switch and Mattermost must provide real human-agent and agent-agent collaboration. DoorLoop is deferred; use fictional seed data.

## Product acceptance criteria

### Individual landlord

- A tenant submits a complaint to their owner with property and request context.
- Agents investigate maintenance history, similar issues, warranties, vendor options, and repair estimates, distinguishing evidence from estimates and missing information.
- The owner sees a live, structured timeline of investigation, proposals, decisions, and execution results.
- Consequential actions require backend-verified owner approval before execution.

### Property management team

- Multiple tenants submit requests into a shared operations queue.
- Related requests can link to one incident while preserving original request content and identity.
- Each incident has a human coordinator.
- Specialized agents collaborate with the team and each other through Switch in Mattermost.
- Role-aware approval rules govern vendor communication, scheduling, spending, and closure.

## Checkpoint 1 — Switch and Mattermost connectivity

### Prerequisites and decisions

- Identify the exact Switch project/provider, official documentation, stable SDK or API, supported agent collaboration model, authentication, and Mattermost integration contract. The name alone does not establish these details.
- Obtain the hackathon integration requirements and any required Switch account, workspace, endpoint, credentials, or registration permissions.
- Obtain an authorized Mattermost development instance, reachable server URL, bot identity/token or supported authentication alternative, team/channel identifiers, and permission to post development test messages.
- Confirm whether Mattermost is hosted or local, its supported version, bot permissions, and any required incoming/outgoing integration configuration.
- Determine callback/webhook requirements from the actual integration contract, including reachable URLs, event authentication, TLS, and local development networking if needed. Do not assume webhooks are required.
- Confirm available Python, package tooling, and development infrastructure. Verify compatible stable dependency versions against official sources before installation; pin the chosen versions reproducibly.
- Establish environment variable names and secret handling after verifying the provider contracts. Document placeholders only.
- Decide the minimal connectivity proof and identify its test channel and human participant. No vendor contact, scheduling, spending, or request closure is permitted in the connectivity proof.

### Tasks after review authorization

1. Review official Switch and Mattermost documentation and record the selected contracts and dependency compatibility evidence.
2. Create the smallest backend/development scaffold needed for connectivity, configuration validation, and replaceable integration adapters.
3. Authenticate to both services and verify required permissions and channel access.
4. Demonstrate an agent message reaching the authorized Mattermost channel through the intended Switch path, a human reply reaching the agent, and one agent-to-agent exchange through Switch. Verify supported correlation and event delivery behavior.
5. Handle unavailable services, invalid credentials, rejected permissions, and duplicate events where applicable, without false success or secret leakage.
6. Record reproducible setup and live verification evidence, run applicable tests, and update PROGRESS.md.

### Acceptance criteria

- Real Switch and Mattermost connectivity is demonstrated with recorded, non-secret evidence; a mocked response is insufficient.
- Human-agent round trip and agent-agent exchange use the intended integration path and retain enough identifiers to correlate events.
- Configuration failures and integration errors are explicit. Automated checks cover adapter/configuration failures and event handling behavior introduced in this checkpoint.
- Setup is reproducible and credentials remain outside tracked files and logs.
- Missing access is reported as a blocker rather than represented as a completed integration.

## Checkpoint 2 — Core maintenance models, APIs, and seeded history

Tasks: define domain relationships and explicit states; add SQLAlchemy persistence and schema management; expose thin APIs through services; seed fictional tenants, owners, teams, properties, requests, incidents, maintenance history, warranties, and vendors as needed for the demo. Establish identity and role boundaries needed by later workflows.

Acceptance: persistent request creation and retrieval work; relationships and ownership constraints are enforced; seeds are reproducible; invalid input and unauthorized access are tested; history is available for investigation. Preserve original requests when incident linking is introduced.

## Checkpoint 3 — Agent investigation

Tasks: implement triage, history, and vendor investigation using replaceable integrations; include similar issues, warranty context, and repair estimates; produce structured activity and evidence; use Switch collaboration from Checkpoint 1.

Acceptance: seeded scenarios yield traceable findings and proposals; uncertain estimates and unavailable evidence are labeled; investigation performs no consequential external action; agent/tool failures remain visible and recoverable. Test orchestration and failure behavior.

## Checkpoint 4 — Approval enforcement and individual-owner workflow

Tasks: implement proposal, approval/rejection, and execution services; bind approval to actor, role, action, and current action details; define approval invalidation and action state transitions; enforce authorization at execution; add idempotent retries and structured owner timeline delivery.

Acceptance: an individual tenant-to-owner scenario completes with investigation and an approved action; unapproved, unauthorized, stale, changed, and replayed action attempts cannot bypass policy or execute twice. Denials and execution failures appear in the timeline. Tests exercise backend enforcement independently of UI controls.

## Checkpoint 5 — Team incident coordination and React dashboard

Tasks: implement shared queue, incident grouping, coordinator assignment, team roles and approval policies; build React/TypeScript individual and team views; connect structured live activity and Mattermost collaboration to domain records.

Acceptance: multiple requests can link to one coordinator-owned incident without losing originals; role rules govern vendor communication, scheduling, spending, and closure; dashboard displays queue, request/incident context, investigation, approvals, and live status. Test domain permissions and meaningful frontend workflows and failures.

## Checkpoint 6 — Integration testing, demo, and submission

Tasks: run end-to-end scenarios for both modes; exercise real Switch/Mattermost collaboration and failure recovery; validate approval enforcement and duplicate-event behavior; prepare fictional demo data, setup instructions, demo script, and submission materials against verified hackathon requirements.

Acceptance: both modes are demonstrated with recorded test results and honest integration status; no consequential external action bypasses backend approval; setup and demo are reproducible; remaining limitations and blockers are documented; submission requirements are checked against official hackathon materials.

## Open decisions

- Exact Switch provider and documentation; hackathon rules and submission details.
- Development service access, credentials, permissions, and hosting/networking.
- Application identity/authentication approach, role matrix, spending authority, and action-specific approval policies.
- Agent/model provider and access; estimate evidence and vendor execution scope for the fictional demo.

Resolve each decision before the implementation step that depends on it. These are open decisions, not implemented capabilities.
