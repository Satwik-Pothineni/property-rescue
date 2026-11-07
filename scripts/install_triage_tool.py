"""Give only the pr-triage Switch agent the Property Rescue evidence tool (Codex MCP).

Writes ~/.switch/agents/pr-triage/.codex/config.toml (Codex project config, read
only for trusted directories) and adds a trust entry for that single directory to
~/.codex/config.toml after backing it up. pr-history and pr-vendors are unchanged.
Restart the pr-triage session in Switch Console afterwards.

Usage: .venv/bin/python scripts/install_triage_tool.py [--mattermost-user USERNAME] [--app-user ALIAS]
Defaults: Mattermost human from .local/switch/.env, app user `owner`.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys
import urllib.request
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = Path.home() / ".switch/agents/pr-triage"
GLOBAL = Path.home() / ".codex/config.toml"


def env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))


def mattermost_user_id(username: str) -> str:
    app = env(ROOT / ".local/app/.env")
    request = urllib.request.Request(f"{app['MATTERMOST_URL']}/api/v4/users/username/{username}",
                                     headers={"Authorization": "Bearer " + app["MATTERMOST_TOKEN"]})
    with urllib.request.urlopen(request, timeout=10) as response:
        user = json.load(response)
    if user.get("is_bot"):
        raise SystemExit(f"{username} is a bot; investigations must be started by a human")
    return user["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mattermost-user", default=env(ROOT / ".local/switch/.env")["MATTERMOST_USER"])
    parser.add_argument("--app-user", default="owner", help="demo alias whose property access commands use")
    args = parser.parse_args()
    if not AGENT_DIR.is_dir():
        raise SystemExit(f"{AGENT_DIR} not found; create the agents from investigation.template.yaml first")
    python, launcher = ROOT / ".venv/bin/python", ROOT / "scripts/agent_evidence_mcp.py"
    app_user = uuid5(NAMESPACE_URL, "property-rescue/fictional-demo/v1/" + args.app_user)
    config = (
        "# Written by Property Rescue scripts/install_triage_tool.py. Only pr-triage reads this.\n"
        "[mcp_servers.property_rescue]\n"
        f"command = {json.dumps(str(python))}\n"
        f"args = {json.dumps([str(launcher), '--mattermost-user-id', mattermost_user_id(args.mattermost_user), '--app-user-id', str(app_user)])}\n"
        'enabled_tools = ["investigate_request", "sync_investigation"]\n'
        'default_tools_approval_mode = "approve"\n'
        "startup_timeout_sec = 30\n"
    )
    (AGENT_DIR / ".codex").mkdir(exist_ok=True)
    (AGENT_DIR / ".codex/config.toml").write_text(config)
    trust = f'[projects."{AGENT_DIR}"]\ntrust_level = "trusted"\n'
    current = GLOBAL.read_text() if GLOBAL.exists() else ""
    if f'[projects."{AGENT_DIR}"]' not in current:
        if GLOBAL.exists():
            shutil.copy2(GLOBAL, GLOBAL.with_name("config.toml.before-property-rescue"))
        GLOBAL.write_text(current.rstrip("\n") + "\n\n" + trust)
    print(f"Installed for pr-triage only ({AGENT_DIR}). Backup: {GLOBAL.with_name('config.toml.before-property-rescue')}.")
    print("Now update pr-triage's instructions from investigation.template.yaml in Switch Console and restart its session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
