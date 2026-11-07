"""Prepare the official release's local stack; never print generated secrets."""

from pathlib import Path
import re
import secrets
from urllib.request import urlopen
from urllib.error import URLError


RELEASE = "switch-console-v0.40.1"
BASE = f"https://raw.githubusercontent.com/sandbox-quantum/switch/{RELEASE}/"
DEST = Path(__file__).resolve().parents[1] / ".local" / "switch"


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (DEST / ".env").exists():
        raise SystemExit("Local Switch configuration already exists; left unchanged.")
    paths = {
        "compose.yaml": "console/apps/switch-console-desktop/src/main/core/managed-switch-server/resources/standalone-docker-compose.pinned.yml",
        ".env": ".env.example",
    }
    # Fetch everything before creating files. No credentials travel in these requests.
    downloaded = {}
    for name, path in paths.items():
        try:
            with urlopen(BASE + path, timeout=30) as response:
                downloaded[name] = response.read().decode("utf-8")
        except (URLError, OSError):
            raise SystemExit("Cannot download official Switch files; check network access.") from None
    values = {key: secrets.token_hex(24) for key in (
        "DB_PASSWORD", "DB_OWNER_PASSWORD", "AGENT_REGISTRATION_TOKEN",
        "GATEWAY_ADMIN_PASSWORD", "MATTERMOST_ADMIN_PASSWORD", "MATTERMOST_USER_PASSWORD",
    )}
    values.update(SECRET_KEYS="local:" + secrets.token_hex(32), SWITCH_VERSION="0.31.0",
                  FRONTEND_BASE_URL="http://localhost:3000")
    for key, value in values.items():
        downloaded[".env"], count = re.subn(rf"^{key}=.*$", f"{key}={value}", downloaded[".env"], flags=re.MULTILINE)
        if count != 1:
            raise SystemExit(f"Upstream configuration changed: expected one {key} field")
    downloaded[".env"] += "\nSWITCH_BIND_ADDR=127.0.0.1\nTELEMETRY_ENABLED=false\nTHIRD_PARTY_AVATARS_ENABLED=false\n"
    for name, content in downloaded.items():
        with (DEST / name).open("x") as output:
            (DEST / name).chmod(0o600)
            output.write(content)
    print("Official stack prepared in .local/switch; credentials saved locally, not displayed.")


if __name__ == "__main__":
    main()
