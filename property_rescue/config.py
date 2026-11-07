"""Validate environment configuration without displaying secret values."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from urllib.parse import urlsplit
from uuid import UUID


class ConfigurationError(ValueError):
    """Configuration cannot safely be used for a live proof."""


def required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value or any(ord(char) < 32 for char in value):
        raise ConfigurationError(f"Set a valid {name} locally")
    return value


def mattermost_origin(env: Mapping[str, str]) -> str:
    url = required(env, "MATTERMOST_URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise ConfigurationError("Invalid MATTERMOST_URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port == 0
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise ConfigurationError("MATTERMOST_URL must be an HTTPS origin or local HTTP origin")
    return url.rstrip("/")


def mattermost_token(env: Mapping[str, str]) -> str:
    token = required(env, "MATTERMOST_TOKEN")
    if not token.isascii() or any(char.isspace() for char in token):
        raise ConfigurationError("Invalid MATTERMOST_TOKEN")
    return token


@dataclass(frozen=True)
class Settings:
    mattermost_url: str
    token: str = field(repr=False)
    human: str
    coordinator: str
    worker: str
    root_id: str
    run_id: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        url = mattermost_origin(env)
        names = [required(env, key) for key in ("PROOF_HUMAN", "PROOF_COORDINATOR", "PROOF_WORKER")]
        if len(set(names)) != 3 or any(not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", name) for name in names):
            raise ConfigurationError("Proof usernames must be distinct valid Mattermost usernames")
        root_id = required(env, "PROOF_ROOT_ID")
        if not re.fullmatch(r"[a-z0-9]{26}", root_id):
            raise ConfigurationError("PROOF_ROOT_ID must be a Mattermost post ID")
        run_id = required(env, "PROOF_RUN_ID")
        try:
            if str(UUID(run_id)) != run_id:
                raise ValueError
        except ValueError:
            raise ConfigurationError("PROOF_RUN_ID must be a canonical UUID") from None
        return cls(url, mattermost_token(env), *names, root_id, run_id)
