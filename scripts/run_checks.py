"""Run every automated and live check and record the outcome in docs/CHECK_RESULTS.md.

Usage (project root, API on 8100 already running; dashboard on 5173 optional):
    .venv/bin/python scripts/run_checks.py --run-id YOUR_INVESTIGATION_UUID

Live failure checks start short-lived extra API instances on port 8101 with a
deliberately invalid Mattermost token and an unreachable Mattermost URL, then
stop them. Nothing is posted to Mattermost. Tokens are never printed or recorded.
"""

import argparse
from uuid import UUID
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = ""  # Selected explicitly; never assume a developer database record exists.
TOKENS = json.loads((ROOT / ".local/app/demo-tokens.json").read_text())
UV = shutil.which("uv") or str(ROOT / ".local/uv-aarch64-apple-darwin/uv")
ENV = os.environ | {"UV_CACHE_DIR": str(ROOT / ".uv-cache"), "UV_PYTHON_INSTALL_DIR": str(ROOT / ".local/python")}
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, evidence: str) -> None:
    results.append((name, ok, evidence))
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {evidence}", flush=True)


def run(command: list[str], cwd: Path = ROOT, timeout: int = 900) -> tuple[int, str]:
    done = subprocess.run(command, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout)
    return done.returncode, done.stdout + done.stderr


def http(method: str, url: str, alias: str, body=None) -> tuple[int, object]:
    request = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + TOKENS[alias], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, json.load(error)


def up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3):
            return True
    except (urllib.error.URLError, OSError):
        return False


def automated() -> None:
    code, out = run([UV, "run", "--locked", "--env-file", ".local/app/.env", "python", "-W", "error::ResourceWarning",
                     "-m", "unittest", "discover", "-s", "tests"])
    ran = re.search(r"Ran (\d+) tests in ([\d.]+)s", out)
    record("Backend unit + PostgreSQL integration tests", code == 0 and "OK" in out.splitlines()[-1],
           f"{ran.group(1)} tests, {'OK' if code == 0 else 'FAILED'} in {ran.group(2)}s" if ran else out[-300:])
    code, out = run([UV, "run", "--locked", "--env-file", ".local/app/.env", "alembic", "check"])
    record("Migrations match models", code == 0, out.strip().splitlines()[-1] if out.strip() else f"exit {code}")
    frontend = ROOT / "frontend"
    for label, command in (("Frontend typecheck", ["npx", "tsc", "--noEmit"]), ("Frontend tests", ["npx", "vitest", "run"]),
                           ("Frontend production build", ["npm", "run", "build"])):
        code, out = run(command, cwd=frontend)
        summary = re.search(r"Tests\s+(\d+ passed[^\n]*)", out)
        record(label, code == 0, summary.group(1).strip() if summary else ("ok" if code == 0 else out[-300:]))


def scenarios() -> None:
    team_base = "http://127.0.0.1:5173/api" if up("http://127.0.0.1:5173/") else "http://127.0.0.1:8100"
    for label, script, base in (("Individual mode end to end (owner scenario)", "demo_owner_workflow.py", "http://127.0.0.1:8100"),
                                ("Team mode end to end (team scenario)", "demo_team_workflow.py", team_base)):
        code, out = run([sys.executable, f"scripts/{script}", base])
        passes = out.count("\nPASS") + out.startswith("PASS")
        record(label, code == 0 and "ALL CHECKS PASSED" in out,
               f"{passes} checks passed via {base}" + ("" if code == 0 else " — " + out[-400:]))


def live_switch() -> None:
    base = "http://127.0.0.1:8100"
    first = http("POST", f"{base}/investigations/{RUN_ID}/collaboration/sync", "owner", {})
    second = http("POST", f"{base}/investigations/{RUN_ID}/collaboration/sync", "owner", {})
    if first[0] == 503:
        record("Live Switch thread import from Mattermost", False, "Mattermost not configured; run scripts/connect_mattermost.py")
        return
    messages = first[1] if isinstance(first[1], list) else []
    agents = sorted({m["sender"] for m in messages if m["sender_is_bot"]})
    tags = [m["tag"] for m in messages if m["tag"]]
    record("Live Switch thread import from Mattermost", first[0] == 200 and "INV_REPORT" in tags,
           f"HTTP {first[0]}; {len(messages)} posts; agents {', '.join(agents)}; tags {' → '.join(tags)}")
    same = isinstance(second[1], list) and [m["post_id"] for m in second[1]] == [m["post_id"] for m in messages]
    record("Duplicate sync imports nothing twice", second[0] == 200 and same, f"HTTP {second[0]}; identical {len(messages)} posts")
    status, run_view = http("GET", f"{base}/investigations/{RUN_ID}", "owner")
    record("Agent report linked to investigation record", status == 200 and run_view.get("agent_review") == "report_received",
           f"agent_review={run_view.get('agent_review')}")
    for alias, expected in (("tenant", 403), ("other_owner", 404)):
        status, _ = http("POST", f"{base}/investigations/{RUN_ID}/collaboration/sync", alias, {})
        record(f"Sync refused for {alias}", status == expected, f"HTTP {status}")


def failure_recovery() -> None:
    """Real failures: Mattermost rejecting a bad token, and Mattermost unreachable."""
    app_env = dict(line.split("=", 1) for line in (ROOT / ".local/app/.env").read_text().splitlines() if "=" in line)
    real_token = app_env.get("MATTERMOST_TOKEN", "")
    for label, override, expect in (("Invalid Mattermost token", {"MATTERMOST_TOKEN": "invalid0token0for0failure0check"}, "HTTP 401"),
                                    ("Mattermost unreachable", {"MATTERMOST_URL": "http://127.0.0.1:9"}, "connection failed")):
        env = ENV | app_env | override
        server = subprocess.Popen([UV, "run", "--locked", "uvicorn", "property_rescue.api:create_app", "--factory",
                                   "--host", "127.0.0.1", "--port", "8101", "--no-access-log"],
                                  cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                if up("http://127.0.0.1:8101/openapi.json"):
                    break
                time.sleep(0.5)
            status, body = http("POST", f"http://127.0.0.1:8101/investigations/{RUN_ID}/collaboration/sync", "owner", {})
            text = json.dumps(body)
            leaked = bool(real_token) and real_token in text or "invalid0token" in text
            record(f"Failure: {label} reported, not hidden", status == 502 and expect in text and not leaked,
                   f"HTTP {status}: {body.get('detail') if isinstance(body, dict) else body}; secret echoed: {leaked}")
        finally:
            server.terminate()
            server.wait(timeout=20)
    status, body = http("GET", f"http://127.0.0.1:8100/investigations/{RUN_ID}", "owner")
    record("Recovery: healthy API unaffected after failures", status == 200 and body.get("agent_review") == "report_received",
           f"HTTP {status}; agent_review={body.get('agent_review') if isinstance(body, dict) else '?'}")


def write_report(started: datetime) -> None:
    passed = sum(ok for _, ok, _ in results)
    lines = [
        "# Check results", "",
        f"Generated by `scripts/run_checks.py` on {started:%Y-%m-%d %H:%M} UTC. "
        f"**{passed}/{len(results)} passed.** All data is fictional. No tokens are recorded.", "",
        "Live checks use the real local Switch/Mattermost stack and PostgreSQL. The Switch agent run itself",
        "happens in Switch Console; these checks import and verify its Mattermost thread. Vendor, calendar",
        "and payment execution is a labelled fictional adapter (`delivery: not_sent`).", "",
        "| Check | Result | Evidence |", "| --- | --- | --- |",
    ] + [f"| {name} | {'PASS' if ok else 'FAIL'} | {evidence.replace('|', '/')} |" for name, ok, evidence in results]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/CHECK_RESULTS.md").write_text("\n".join(lines) + "\n")
    print(f"\n{passed}/{len(results)} passed. Recorded in docs/CHECK_RESULTS.md")


def main() -> int:
    global RUN_ID
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, type=UUID,
                        help="Investigation UUID whose real Switch thread should be verified")
    RUN_ID = str(parser.parse_args().run_id)
    started = datetime.now(timezone.utc)
    if not up("http://127.0.0.1:8100/openapi.json"):
        raise SystemExit("Start the API on port 8100 first (see README).")
    automated()
    scenarios()
    live_switch()
    failure_recovery()
    write_report(started)
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
