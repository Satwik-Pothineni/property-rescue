"""Read-only Mattermost API access. Switch owns all agent message delivery."""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


class IntegrationError(RuntimeError):
    """Sanitized integration failure; never includes response bodies or tokens."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        # Never forward bearer credentials to a redirected origin.
        return None


class MattermostReader:
    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url
        self._token = token
        self._opener = build_opener(NoRedirect())

    def _get(self, path: str) -> dict[str, Any]:
        request = Request(
            self._base_url + "/api/v4" + path,
            headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise IntegrationError("Mattermost response exceeded the proof size limit")
            result = json.loads(raw)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise IntegrationError(f"Mattermost request rejected (HTTP {status})") from None
        except (URLError, TimeoutError, OSError):
            raise IntegrationError("Mattermost connection failed; check service availability and TLS") from None
        except (ValueError, UnicodeError):
            raise IntegrationError("Mattermost returned invalid JSON") from None
        if not isinstance(result, dict):
            raise IntegrationError("Mattermost returned an unexpected response shape")
        return result

    def user(self, username: str) -> dict[str, Any]:
        return self._get("/users/username/" + quote(username, safe=""))

    def thread(self, root_id: str) -> dict[str, Any]:
        return self._get("/posts/" + quote(root_id, safe="") + "/thread")

    def user_by_id(self, user_id: str) -> dict[str, Any]:
        return self._get("/users/" + quote(user_id, safe=""))

    def channel_posts(self, channel_id: str) -> dict[str, Any]:
        posts: dict[str, Any] = {}
        before = ""
        for _ in range(1000):
            path = "/channels/" + quote(channel_id, safe="") + "/posts?per_page=200"
            if before:
                path += "&before=" + quote(before, safe="")
            page = self._get(path)
            order, batch = page.get("order"), page.get("posts")
            if not isinstance(order, list) or not isinstance(batch, dict):
                raise IntegrationError("Mattermost returned an unexpected response shape")
            if not order:
                return {"posts": posts, "order": list(posts)}
            if any(not isinstance(pid, str) or pid not in batch for pid in order):
                raise IntegrationError("Mattermost returned an unexpected response shape")
            if order[-1] == before or not set(order) - posts.keys():
                raise IntegrationError("Mattermost pagination did not advance")
            posts.update(batch)
            before = order[-1]
        raise IntegrationError("Mattermost channel history exceeded the sync limit")
