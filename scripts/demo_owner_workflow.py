"""Run the Checkpoint 4 individual-owner scenario against a running API.

Usage: python scripts/demo_owner_workflow.py [base_url]   (default http://127.0.0.1:8100)

Creates one new fictional request on the seeded cottage and closes it through an
approved action. Seeded requests are untouched. Tokens are read locally, never printed.
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
COTTAGE = uuid5(NAMESPACE_URL, "property-rescue/fictional-demo/v1/cottage")
VENDOR = uuid5(NAMESPACE_URL, "property-rescue/fictional-demo/v1/cottage/vendor")
failures = 0


def call(method, path, alias, body=None, key=None):
    headers = {"Authorization": "Bearer " + TOKENS[alias], "Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = str(key)
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
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
    return body


def decision(action, alias="owner"):
    return call("POST", f"/actions/{action['id']}/decision", alias,
                {"decision": "approved", "revision": action["revision"], "details_hash": action["details_hash"]})


def main() -> int:
    with urllib.request.urlopen(BASE + "/openapi.json", timeout=10) as response:
        if "/actions/{action_id}/execution" not in json.load(response)["paths"]:
            print(f"The API at {BASE} is running older code without Checkpoint 4 routes. Restart it (see README).")
            return 2
    s, req = call("POST", "/requests", "tenant", {"property_id": str(COTTAGE), "title": "Kitchen tap is dripping",
        "description": "Fictional demo: the cold tap drips overnight.", "category": "plumbing"}, uuid4())
    check("1. Tenant submits complaint", s, 201, req)
    rid = req["id"]
    s, body = call("PUT", f"/requests/{rid}/acknowledgement", "owner")
    check("2. Owner acknowledges", s, 200, body)
    s, run = call("POST", f"/requests/{rid}/investigations", "owner", key=uuid4())
    check("3. Evidence investigation completes", s, 200, run, run.get("status") == "ready_for_review")
    proposal = {"investigation_id": run["id"], "rationale": "Fictional: vendor listed for plumbing in the packet.",
                "evidence_ids": [f"vendor:{VENDOR}"],
                "details": {"kind": "contact_vendor", "vendor_id": str(VENDOR),
                            "message": "Fictional demo: please quote a dripping cold-tap repair."}}
    s, action = call("POST", f"/requests/{rid}/actions", "owner", proposal, uuid4())
    check("4. Owner proposes vendor contact", s, 201, action, action.get("status") == "proposed")
    aid = action["id"]

    s, body = call("POST", f"/actions/{aid}/execution", "owner", key=uuid4())
    check("5. Execute before approval is refused", s, 409, body)
    s, body = call("GET", f"/actions/{aid}", "other_owner")
    check("6a. Unrelated owner cannot see the action", s, 404, body)
    s, body = decision(action, "tenant")
    check("6b. Tenant cannot approve", s, 403, body)
    s, approved = decision(action)
    check("7. Owner approves revision 1", s, 200, approved, approved.get("status") == "approved")

    revision = {"expected_revision": 1, "rationale": proposal["rationale"], "evidence_ids": proposal["evidence_ids"],
                "details": proposal["details"] | {"message": "Fictional demo: also inspect the shower valve."}}
    s, changed = call("PUT", f"/actions/{aid}", "owner", revision)
    check("8a. Changing details resets approval", s, 200, changed,
          (changed.get("revision"), changed.get("status")) == (2, "proposed"))
    s, body = call("POST", f"/actions/{aid}/execution", "owner", key=uuid4())
    check("8b. Old approval cannot execute changed action", s, 409, body)
    s, body = decision(approved)
    check("8c. Approving the stale revision is refused", s, 409, body)

    s, approved = decision(changed)
    check("9a. Owner approves revision 2", s, 200, approved)
    key = uuid4()
    s, done = call("POST", f"/actions/{aid}/execution", "owner", key=key)
    check("9b. Approved action executes", s, 200, done, done.get("status") == "executed")
    print("      result:", json.dumps(done.get("result")))
    s, again = call("POST", f"/actions/{aid}/execution", "owner", key=key)
    check("10a. Retry with same key returns same result", s, 200, again, again == done)
    s, body = call("POST", f"/actions/{aid}/execution", "owner", key=uuid4())
    check("10b. Second execution with new key refused", s, 409, body)

    s, close = call("POST", f"/requests/{rid}/actions", "owner", {"investigation_id": run["id"],
        "rationale": "Fictional: repair complete.", "evidence_ids": [f"request:{rid}"],
        "details": {"kind": "close_request", "resolution": "Fictional demo: tenant confirmed the drip stopped."}}, uuid4())
    check("11a. Owner proposes closure", s, 201, close)
    s, close = decision(close)
    s, closed = call("POST", f"/actions/{close['id']}/execution", "owner", key=uuid4())
    check("11b. Approved closure executes", s, 200, closed, closed.get("status") == "executed")
    s, tenant_view = call("GET", f"/requests/{rid}", "tenant")
    check("11c. Tenant sees request closed, original text intact", s, 200, tenant_view,
          tenant_view.get("status") == "closed" and tenant_view.get("title") == "Kitchen tap is dripping")

    s, events = call("GET", f"/requests/{rid}/timeline", "owner")
    check("12. Owner timeline is ordered and gapless", s, 200, events,
          [e["sequence"] for e in events] == list(range(1, len(events) + 1)))
    print(f"\nOwner timeline for request {rid}:")
    for e in events:
        d = e["details"]
        extra = d.get("reason") or " ".join(filter(None, (d.get("step"), d.get("status")))) or d.get("action_kind", "")
        print(f"  {e['sequence']:>3}  {e['kind']:<32} {e['actor_role'] or 'system':<8} {extra}")
    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
