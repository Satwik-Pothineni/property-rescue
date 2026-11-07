# Property Rescue

**AI agents investigate maintenance problems. People make the decisions.**

If you manage rental properties, every repair raises the same questions: who fixed
this last time, is it still under warranty, which vendor do we call, and what should
it cost? The answers are scattered across old emails, spreadsheets and memory.

Property Rescue gives landlords and property management teams a small team of AI
agents that dig up those answers together, in your team's chat room, through
**Switch**. The agents never act on their own: contacting a vendor, booking a
visit, spending money or closing a request always needs approval from the right
person, and the app checks that approval before anything happens.

Built for the WeMakeDevs **Flip the Switch** hackathon (Nov 4–7, 2026), Track 01: Best
Business Workflow. All people, properties, vendors and costs are fictional.

## Demo video

**▶ https://youtu.be/py_b3An0K7A** (2 minutes)

## How it works

1. A **tenant** reports a problem in the app.
2. It lands in a **shared queue**. If several tenants report the same outage, a
   coordinator groups them into one **incident**. Nobody's original message is lost.
3. The owner or coordinator **collects the evidence**: past repairs, warranties,
   vendors and cost allowances. Every finding shows where it came from.
4. They post **one message in a private Mattermost room**, and three AI agents take
   the case through Switch:
   - **pr-triage** reads the case and hands out the work,
   - **pr-history** checks past repairs, similar complaints and warranties,
   - **pr-vendors** checks vendors and cost allowances.

   They talk to each other in the same thread, and pr-triage posts one report
   where every claim cites its source.
5. The conversation is pulled back into the app, onto the request's **live timeline**.
6. A person **proposes an action** (contact a vendor, schedule a visit, approve
   spending, close the request). The **right person approves it**, and only then can
   it run, exactly once.

Without Switch there is no investigation: no agents, no hand-offs, no report.

---

## Set it up (about 20 minutes)

You'll use three windows: **VS Code** (terminal), **Switch Console** (runs the
agents) and **Mattermost** in your browser (where people and agents talk).

### What you need

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), running
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (installs Python for you)
- [Node.js](https://nodejs.org/) 22.12 or newer
- [Switch Console 0.40.1](https://github.com/sandbox-quantum/switch) with an agent
  provider signed in: **Codex** or **Claude Code**

### 1. Get the code (VS Code)

Open VS Code, then **Terminal → New Terminal** and run:

```sh
git clone https://github.com/Satwik-Pothineni/property-rescue.git
cd property-rescue
code .
uv sync --locked
```

### 2. Start Switch and Mattermost (VS Code terminal)

```sh
uv run --locked python scripts/prepare_switch.py
docker compose --project-name property-rescue-switch --env-file .local/switch/.env -f .local/switch/compose.yaml --profile collab --profile gateway up -d
```

This downloads the official Switch setup and starts Switch, its gateway and
Mattermost in Docker. Passwords are generated for you and kept in `.local/`
(never committed).

### 3. Start the app's database and load the demo data (VS Code terminal)

```sh
uv run --locked python scripts/prepare_app.py
docker compose --env-file .local/app/.env up -d --wait
uv run --locked --env-file .local/app/.env alembic upgrade head
uv run --locked --env-file .local/app/.env python -m property_rescue.seed
```

This creates fictional landlords, tenants, properties, past repairs, warranties
and vendors, plus sign-in keys for each demo person in `.local/app/demo-tokens.json`.

### 4. Create the agents (Switch Console)

1. Open Switch Console and choose **Connect to an existing server**: `http://localhost:8000`.
2. Import a template file from this repo:
   - `investigation.template.yaml` if you use **Codex**, or
   - `investigation-claude.template.yaml` if you use **Claude Code**.
3. Click **Use template**, choose your provider, **Local** and the **Mattermost** bridge,
   and create it.

Switch creates the three agents and a private Mattermost room for them.

### 5. Join the room (Mattermost)

1. Open **http://localhost:8065**.
2. Sign in as the human user. The username and password are `MATTERMOST_USER` and
   `MATTERMOST_USER_PASSWORD` in `.local/switch/.env`.
3. Open the private channel **property-rescue-investigation** (or
   **property-rescue-investigation-claude**). You should see the three agents in it.

### 6. Connect the app to the room and start it (VS Code terminal)

```sh
uv run --locked python scripts/connect_mattermost.py
uv run --locked --env-file .local/app/.env uvicorn property_rescue.api:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

The first command lets the app read the agents' room. The second starts the app's
server, so leave this terminal running.

Open a **second terminal** (the **+** in VS Code's terminal panel) and start the dashboard:

```sh
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. To sign in, copy a key from
`.local/app/demo-tokens.json`: `tenant`, `owner`, `coordinator` (Robin) or
`coordinator_two` (Riley). Use a separate private browser window for each person.

**Optional (Codex only), so the one-line command works:** give pr-triage the
evidence tool, then restart the pr-triage session in Switch Console.

```sh
uv run --locked python scripts/install_triage_tool.py
```

Without it, use **Copy brief for Switch agents** in step 5 of the demo instead; the
agents then get the evidence in the message itself.

---

## Try the demo yourself

Each step says what you do and what it shows.

**1. Report a problem (as `tenant`).**
Fill in *Report a problem*: home, category *plumbing*, title "Kitchen tap is
dripping", a short description. Click **Send request**.
*This is all a tenant ever does. They only see their own requests and status.*

**2. See the queue (as `owner`, new window).**
The request appears in the queue. Click it: the tenant's original words are shown
and can't be changed.

**3. Group a shared problem (as `coordinator`, new window).**
Tick two heating requests from the Fictional Apartments, type a title such as
"Boiler outage", pick a coordinator, click **Create incident**.
*Related complaints become one incident with one person in charge, and each
tenant's request stays intact.*

**4. Collect the evidence (as `owner`).**
Open the tap request, click **Acknowledge**, then **Collect evidence here**. Open
the *triage*, *history* and *vendors* sections.
*Each finding is tagged (for example "uncertain" or "missing") and lists the
records it came from.*

**5. Hand it to the agents (owner → Mattermost).**
Click **Copy agent command** and paste it as a message in the Mattermost room
(it looks like `@pr-triage investigate …`). Or click **Copy brief for Switch agents**
and paste that instead.
*This is where Switch takes over.*

**6. Watch the agents work (Mattermost).**
In the thread, pr-triage acknowledges the case and sends one task to pr-history and
one to pr-vendors. Each replies with what it found, and pr-triage posts the final
report. It usually takes 1–2 minutes. Click **Show activity** under an agent to see
what it did.
*No agent can contact anyone or spend anything. They can only talk in the room.*

**7. Bring the conversation into the app (as `owner`).**
Back on the request, click **Sync agent discussion from Mattermost**. The agents'
messages appear under *Agent discussion*, and the **Timeline** gains an entry for each.
*The agents' work becomes part of the request's record.*

**8. Propose an action and approve it (as `owner`).**
Under *Propose an action*, choose **Contact vendor**, pick the vendor, write a short
message and reason, tick a piece of evidence, and click **Submit proposal**. Then
click **Approve revision 1** and **Execute**.
*The result says "fictional – nothing sent": the demo never contacts real vendors.
The timeline shows proposed → approved → executed.*

**9. See the rules hold (as `coordinator`).**
On a request in the incident, propose **Authorize spending** of USD 750 and try to
approve it as a coordinator. You'll see **Refused**: spending above the team's USD 500
limit needs the owner, and only the incident's own coordinator may approve its other
actions. Approve it as `owner` and it goes through.
*The server enforces who may approve what, not just the buttons. Refusals are
logged on the timeline in red.*

**10. Close the request (as `owner`).**
Propose **Close request**, approve, execute. The request shows as *closed*.

---

## Good to know

- Everything is fictional and local. Vendor contact, scheduling and payments are
  recorded but never sent anywhere.
- Sign-in uses demo keys, not real accounts.
- If syncing says *HTTP 401*, run `uv run --locked python scripts/connect_mattermost.py`
  again and restart the server from step 6.
- The agent thread in the demo video is a verified live run
  (`3aafb708-fb03-4fcc-a2bb-dfaa460c8edd`, started with the evidence brief); the
  one-line command starts the same agents and workflow.
- Run all automated checks, with the server running, using
  `.venv/bin/python scripts/run_checks.py --run-id INVESTIGATION_ID` (the ID of a
  finished agent investigation). Results: [docs/CHECK_RESULTS.md](docs/CHECK_RESULTS.md).

Architecture, API endpoints, approval rules, tests and verified versions:
**[docs/TECHNICAL.md](docs/TECHNICAL.md)**.
