"""Create local application configuration without overwriting or printing secrets."""

from pathlib import Path
import secrets

directory = Path(__file__).resolve().parents[1] / ".local" / "app"
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
path = directory / ".env"
if path.exists():
    raise SystemExit("Application environment already exists; left unchanged.")
password = secrets.token_hex(32)
with path.open("x") as output:
    path.chmod(0o600)
    output.write(
        f"APP_DB_PASSWORD={password}\n"
        f"APP_DATABASE_URL=postgresql+psycopg://property_rescue:{password}@127.0.0.1:55432/property_rescue\n"
    )
print("Application environment prepared in .local/app/.env; no secrets displayed.")
