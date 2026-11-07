# Property Rescue — project instructions

## Purpose and scope

Build an AI-powered maintenance operations system for independent landlords and property management teams for the Flip the Switch Hackathon. Follow PLAN.md for scope and acceptance criteria and PROGRESS.md for verified state.

The initial task is documentation only. Stop for user review after creating these documents. Do not begin implementation until the user authorizes it.

## Product rules

- Individual mode: one tenant submits a complaint to one owner. Agents investigate maintenance history, similar issues, warranties, vendors, and repair estimates. Show the owner a live, structured activity timeline. Obtain owner approval before executing consequential actions.
- Team mode: multiple tenants submit requests to a shared queue. Link related requests to incidents without losing original requests. Every incident has a human coordinator. Specialized agents collaborate with humans and one another through actual Switch and Mattermost integrations.
- Enforce role-based approvals for vendor communication, scheduling, spending, and closure.
- Use fictional seeded tenant, property, maintenance, and vendor data for the MVP. Defer DoorLoop until API access is available.

## Architecture and implementation

- Python and FastAPI backend; PostgreSQL and SQLAlchemy persistence; React and TypeScript frontend.
- Use a modular monolith, service-layer business logic, clear domain boundaries, and thin routes.
- Use readable typed code and SOLID principles where useful. Avoid unnecessary dependencies, abstractions, services, and files.
- Inject replaceable integrations. Keep real adapters distinguishable from test doubles and demo fixtures.
- Verify the latest compatible stable dependency versions against official sources before installing. Record selected versions, compatibility constraints, and verification sources. Do not assume that individually latest versions are mutually compatible.
- Implement explicit state transitions, role-aware authorization, and idempotent actions.
- Backend verification of a valid approval is mandatory at the execution boundary for every consequential external action. UI controls, chat messages, and agent assertions alone are insufficient authorization.
- Keep credentials out of source control, logs, documentation, and frontend bundles. Document configuration using placeholders.
- Preserve existing user files. Do not initialize infrastructure, deploy, or create business features as part of the initial documentation task.

## Verification and checkpoint reporting

- Write meaningful tests for domain behavior, failure paths, authorization, transitions, and retries as applicable. Do not create tests that merely mirror implementation.
- Never claim an integration works without evidence from the real integration. Never fabricate passing tests. Label fixtures, test doubles, skipped checks, and unverified assumptions explicitly.
- At the end of every implementation checkpoint, run applicable tests and update PROGRESS.md with changed files, exact checks and results, blockers, and next steps.
- Separate automated tests from live integration checks. Report failures and unavailable infrastructure explicitly.
- Follow the six checkpoints in PLAN.md. Resolve uncertain provider contracts from official documentation before coding against them.
