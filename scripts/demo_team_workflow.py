"""Run the Checkpoint 5 team scenario against a running API (directly or through the dashboard proxy).

Usage: python scripts/demo_team_workflow.py [base_url]
  default http://127.0.0.1:8100; use http://127.0.0.1:5173/api to go through the dashboard's proxy.

Creates two new fictional apartment requests and one incident; seeded records are untouched.
Tokens are read locally and never printed.
"""

import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
from uuid import NAMESPACE_URL, uuid4, uuid5

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100").rstrip("/")
if not BASE.startswith(("http://", "https://")):
    raise SystemExit(f"Usage: python {sys.argv[0]} [base_url]  (got {BASE!r}; base_url must start with http://)")
TOKENS = json.loads(Path(".local/app/demo-tokens.json").read_text())


def demo_id(name):
    return str(uuid5(NAMESPACE_URL, "property-rescue/fictional-demo/v1/" + name))


APARTMENTS, VENDOR = demo_id("apartments"), demo_id("apartments/vendor")
ROBIN, RILEY = demo_id("coordinator"), demo_id("coordinator_two")
failures = 0


def call(method, path, alias, body=None, key=False):
    headers = {"Authorization": "Bearer " + TOKENS[alias], "Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = str(uuid4())
    request = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                     method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.load(error)


def check(label, status, expected, body=None, condition=True):
    global failures
    ok = status == expected and condition
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {label}: HTTP {status}" + ("" if ok else f" (expected {expected}) {body}"))
    return ok


def propose(rid, run, details, alias="member"):
    return call("POST", f"/requests/{rid}/actions", alias, {"investigation_id": run["id"], "details": details,
                "rationale": "Fictional team demo.", "evidence_ids": [f"vendor:{VENDOR}"]}, key=True)


def decide(action, alias):
    return call("POST", f"/actions/{action['id']}/decision", alias,
                {"decision": "approved", "revision": action["revision"], "details_hash": action["details_hash"]})


def main() -> int:
    with urllib.request.urlopen(BASE + "/openapi.json", timeout=10) as response:
        if "/incidents/{incident_id}/coordinator" not in json.load(response)["paths"]:
            print(f"The API at {BASE} is running older code without Checkpoint 5 routes. Restart it (see README).")
            return 2
    complaint = {"property_id": APARTMENTS, "category": "heating", "description": "Fictional: no heat since morning."}
    s1, one = call("POST", "/requests", "tenant", complaint | {"title": "No heat in unit 1"}, key=True)
    s2, two = call("POST", "/requests", "tenant_two", complaint | {"title": "Radiators cold in unit 2"}, key=True)
    check("1. Two tenants submit to the shared queue", s1 if s1 == s2 else 0, 201, (one, two))
    s, queue = call("GET", "/queue", "coordinator")
    check("2. Coordinator queue shows both originals", s, 200, queue, {one["id"], two["id"]} <= {r["request"]["id"] for r in queue})
    s, _ = call("GET", "/queue", "tenant")
    check("2b. Tenant cannot read the queue", s, 403)

    group = {"property_id": APARTMENTS, "title": "Fictional boiler outage", "coordinator_id": ROBIN,
             "request_ids": [one["id"], two["id"]]}
    s, body = call("POST", "/incidents", "member", group, key=True)
    check("3. Team member cannot create incidents", s, 403, body)
    s, incident = call("POST", "/incidents", "coordinator", group, key=True)
    check("4. Coordinator groups both requests under Robin", s, 201, incident,
          {r["title"] for r in incident.get("requests", [])} == {"No heat in unit 1", "Radiators cold in unit 2"})
    s, mine = call("GET", f"/requests/{two['id']}", "tenant_two")
    check("4b. Tenant's original complaint unchanged", s, 200, mine,
          (mine.get("title"), mine.get("description")) == ("Radiators cold in unit 2", complaint["description"]))

    s, run = call("POST", f"/requests/{one['id']}/investigations", "coordinator", key=True)
    check("5. Evidence collected for the incident request", s, 200, run)
    s, contact = propose(one["id"], run, {"kind": "contact_vendor", "vendor_id": VENDOR, "message": "Fictional: boiler check?"})
    check("6. Member proposes vendor contact", s, 201, contact)
    s, body = decide(contact, "coordinator_two")
    check("6b. Non-assigned coordinator cannot approve", s, 403, body)
    s, contact = decide(contact, "coordinator")
    check("6c. Incident coordinator approves", s, 200, contact)

    _, small = propose(one["id"], run, {"kind": "authorize_spend", "vendor_id": VENDOR, "amount": "220.00", "currency": "USD"})
    s, small = decide(small, "coordinator")
    s, done = call("POST", f"/actions/{small['id']}/execution", "coordinator", key=True)
    check("7. Coordinator approves and executes USD 220 (team limit 500)", s, 200, done, done.get("status") == "executed")
    _, large = propose(one["id"], run, {"kind": "authorize_spend", "vendor_id": VENDOR, "amount": "750.00", "currency": "USD"})
    s, body = decide(large, "coordinator")
    check("7b. USD 750 exceeds coordinator limit", s, 403, body)
    s, large = decide(large, "owner")
    check("7c. Owner approves USD 750", s, 200, large)

    s, moved = call("PUT", f"/incidents/{incident['id']}/coordinator", "coordinator", {"coordinator_id": RILEY})
    check("8. Incident reassigned to Riley", s, 200, moved, moved.get("coordinator", {}).get("id") == RILEY)
    s, body = call("POST", f"/actions/{contact['id']}/execution", "owner", key=True)
    check("8b. Robin's unexecuted approval no longer executes", s, 409, body)
    _, visit = propose(one["id"], run, {"kind": "schedule_visit", "vendor_id": VENDOR,
                                       "window_start": "2026-11-10T09:00:00+00:00", "window_end": "2026-11-10T12:00:00+00:00"})
    s, visit = decide(visit, "coordinator_two")
    s, done = call("POST", f"/actions/{visit['id']}/execution", "coordinator_two", key=True)
    check("8c. Riley approves and executes a visit", s, 200, done, done.get("status") == "executed")

    s, body = call("DELETE", f"/incidents/{incident['id']}/requests/{two['id']}", "coordinator_two")
    check("9. Unlink keeps the request in the queue", s, 200, body, [r["id"] for r in body.get("requests", [])] == [one["id"]])

    s, body = call("POST", f"/investigations/{run['id']}/collaboration/sync", "coordinator", {})
    if s == 503:
        print("INFO  10. Mattermost sync not configured (run scripts/connect_mattermost.py); skipped, not counted")
    else:
        check("10. Mattermost sync answered (404 = brief not posted for this run yet)", s, s if s in (200, 404) else 200, body)

    s, events = call("GET", f"/requests/{one['id']}/timeline", "owner")
    kinds = [e["kind"] for e in events]
    check("11. Timeline records grouping, reassignment and denials", s, 200, kinds,
          {"incident.linked", "incident.coordinator_assigned", "action.denied"} <= set(kinds))
    print(f"\nTimeline for '{one['title']}':")
    for e in events:
        d = e["details"]
        print(f"  {e['sequence']:>3}  {e['kind']:<32} {e['actor_role'] or 'system':<8} {d.get('reason') or d.get('action_kind') or d.get('title') or ''}")
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
