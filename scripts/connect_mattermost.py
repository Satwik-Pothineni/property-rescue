"""Give the local API read access to the Switch investigation room. Prints no secrets.

Logs in as the local development human account from .local/switch/.env, finds the
private `property-rescue-investigation` channel and writes MATTERMOST_URL,
MATTERMOST_TOKEN and MATTERMOST_INVESTIGATION_CHANNEL into .local/app/.env (0600).
The API only makes GET requests with this session token. Rerun if it expires.
"""

import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8065"
CHANNEL_NAME = "property-rescue-investigation"


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip("'\"")
    return values


def main() -> int:
    switch = read_env(ROOT / ".local/switch/.env")
    login = urllib.request.Request(BASE + "/api/v4/users/login", method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"login_id": switch["MATTERMOST_USER"], "password": switch["MATTERMOST_USER_PASSWORD"]}).encode())
    try:
        with urllib.request.urlopen(login, timeout=10) as response:
            token = response.headers["Token"]
        lookup = urllib.request.Request(BASE + "/api/v4/users/me/channels",
                                        headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(lookup, timeout=10) as response:
            channels = [c for c in json.load(response) if c.get("name") == CHANNEL_NAME and c.get("delete_at") == 0]
    except urllib.error.HTTPError as error:
        error.close()
        raise SystemExit(f"Mattermost rejected the request (HTTP {error.code}); nothing changed.") from None
    except urllib.error.URLError:
        raise SystemExit("Mattermost is unreachable at " + BASE + "; nothing changed.") from None
    if len(channels) != 1:
        raise SystemExit(f"Expected one '{CHANNEL_NAME}' channel for this user, found {len(channels)}; nothing changed.")

    path = ROOT / ".local/app/.env"
    updates = {"MATTERMOST_URL": BASE, "MATTERMOST_TOKEN": token,
               "MATTERMOST_INVESTIGATION_CHANNEL": channels[0]["id"]}
    kept = [line for line in path.read_text().splitlines() if line.split("=", 1)[0] not in updates]
    temporary = path.with_suffix(".tmp")
    with temporary.open("x") as output:
        temporary.chmod(0o600)
        output.write("\n".join(kept + [f"{k}={v}" for k, v in updates.items()]) + "\n")
    temporary.replace(path)
    print(f"API configured to read channel {channels[0]['id']} ({CHANNEL_NAME}). Token stored privately; restart the API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
