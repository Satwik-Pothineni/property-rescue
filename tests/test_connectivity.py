"""Offline tests use explicit fixtures/local HTTP, never real Switch evidence."""

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import URLError

from property_rescue.config import ConfigurationError, Settings
from property_rescue.messaging import IntegrationError, MattermostReader
from property_rescue.proof import ProofError, main, verify


RUN = "12345678-1234-4234-8234-123456789abc"
ROOT = "a" * 26
ENV = {"MATTERMOST_URL": "http://127.0.0.1:8065", "MATTERMOST_TOKEN": "test-only-secret",
       "PROOF_HUMAN": "human", "PROOF_COORDINATOR": "pr-coordinator", "PROOF_WORKER": "pr-worker",
       "PROOF_ROOT_ID": ROOT, "PROOF_RUN_ID": RUN}


class FixtureReader:
    def __init__(self) -> None:
        self.users = {name: {"username": name, "id": char * 26, "is_bot": index != 0}
                      for index, (name, char) in enumerate(zip(("human", "pr-coordinator", "pr-worker"), "hij"))}
        posts = {}
        for index, (stage, sender, mention) in enumerate((
            ("PR_CONNECT", "h", "@pr-coordinator"), ("PR_ACK", "i", ""),
            ("PR_TASK", "i", "@pr-worker"), ("PR_RESULT", "j", "@pr-coordinator"), ("PR_DONE", "i", ""),
        )):
            post_id = "abcde"[index] * 26
            posts[post_id] = {"id": post_id, "user_id": sender * 26, "root_id": ROOT if index else "",
                              "channel_id": "c" * 26, "create_at": 1000 + index,
                              "message": f"{mention} {stage} {RUN}"}
        self.data = {"posts": posts}

    def user(self, username: str) -> dict:
        return self.users[username]

    def thread(self, root_id: str) -> dict:
        return self.data


class ConfigurationTests(unittest.TestCase):
    def test_valid_configuration_hides_token(self) -> None:
        settings = Settings.from_env(ENV)
        self.assertEqual(settings.root_id, ROOT)
        self.assertNotIn(ENV["MATTERMOST_TOKEN"], repr(settings))

    def test_missing_fields(self) -> None:
        for key in ENV:
            with self.subTest(key=key), self.assertRaises(ConfigurationError):
                Settings.from_env({name: value for name, value in ENV.items() if name != key})

    def test_unsafe_urls_and_identifiers(self) -> None:
        for key, values in {
            "MATTERMOST_URL": ["http://remote.example", "https://user:secret@example.com", "https://example.com/?token=secret", "https://example.com/api", "https://example.com:bad", "file:///tmp/proof"],
            "MATTERMOST_TOKEN": ["secret\nvalue", "secret value", "sëcret"],
            "PROOF_ROOT_ID": ["../secret", "short"], "PROOF_RUN_ID": ["fake", RUN.upper()],
            "PROOF_WORKER": ["human", "@worker"],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ConfigurationError):
                    Settings.from_env(ENV | {key: value})


class ProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings.from_env(ENV)
        self.reader = FixtureReader()

    def test_complete_thread_returns_only_correlation_metadata(self) -> None:
        result = verify(self.settings, self.reader)
        self.assertEqual(len(result["messages"]), 5)
        self.assertEqual(result["root_id"], ROOT)
        self.assertFalse(result["switch_runtime_verified"])
        self.assertNotIn("message", result["messages"][0])
        self.assertNotIn(ENV["MATTERMOST_TOKEN"], json.dumps(result))

    def test_incomplete_or_wrong_run(self) -> None:
        for wrong_run in (False, True):
            reader = FixtureReader()
            if wrong_run:
                reader.data["posts"]["e" * 26]["message"] = "PR_DONE wrong-run"
            else:
                del reader.data["posts"]["e" * 26]
            with self.subTest(wrong_run=wrong_run), self.assertRaises(ProofError):
                verify(self.settings, reader)

    def test_spoofed_edited_deleted_cross_thread_and_out_of_order(self) -> None:
        for key, value in (("user_id", "h" * 26), ("root_id", "z" * 26), ("channel_id", "z" * 26),
                           ("edit_at", 123), ("delete_at", 123), ("create_at", 1), ("create_at", True),
                           ("id", "bad"), ("type", "system_join_channel"), ("message", f"PR_TASK {RUN}")):
            reader = FixtureReader()
            reader.data["posts"]["c" * 26][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ProofError):
                verify(self.settings, reader)

    def test_duplicate_stage_is_rejected(self) -> None:
        post = deepcopy(self.reader.data["posts"]["e" * 26])
        post["id"] = "f" * 26
        self.reader.data["posts"][post["id"]] = post
        with self.assertRaisesRegex(ProofError, "Duplicate"):
            verify(self.settings, self.reader)

    def test_bot_cannot_impersonate_human(self) -> None:
        self.reader.users["human"]["is_bot"] = True
        with self.assertRaises(ProofError):
            verify(self.settings, self.reader)

    def test_malformed_response(self) -> None:
        for data in ({}, {"posts": []}, {"posts": {ROOT: None}}, {"posts": {ROOT: {}}}):
            self.reader.data = data
            with self.subTest(data=data), self.assertRaises(ProofError):
                verify(self.settings, self.reader)

    def test_cli_failure_does_not_report_success(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("sys.stderr", new_callable=io.StringIO) as error:
            self.assertEqual(main(), 1)
            self.assertIn("MATTERMOST_URL", error.getvalue())


class TransportTests(unittest.TestCase):
    def test_real_local_http_contract_and_sanitized_failures(self) -> None:
        # This is an HTTP transport test against a local fixture server,
        # not a live Mattermost integration check.
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                seen.append((self.path, self.headers.get("Authorization")))
                mode = self.server.mode
                self.send_response(mode if isinstance(mode, int) else 200)
                if mode == 302:
                    self.send_header("Location", "/leak")
                self.end_headers()
                self.wfile.write(b'{"id":"test"}' if mode == 200 else b"sensitive-server-error")

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            reader = MattermostReader(f"http://127.0.0.1:{server.server_port}", "test-only-secret")
            server.mode = 200
            self.assertEqual(reader.user("human"), {"id": "test"})
            reader.thread(ROOT)
            self.assertEqual(seen[0], ("/api/v4/users/username/human", "Bearer test-only-secret"))
            self.assertEqual(seen[1][0], f"/api/v4/posts/{ROOT}/thread")
            for mode in (302, 401, 403, 404, 500, "bad-json"):
                server.mode = mode
                with self.subTest(mode=mode), self.assertRaises(IntegrationError) as error:
                    reader.user("human")
                self.assertNotIn("sensitive-server-error", str(error.exception))
                self.assertNotIn("test-only-secret", str(error.exception))
            self.assertFalse(any(path == "/leak" for path, _ in seen))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_network_errors_are_sanitized(self) -> None:
        reader = MattermostReader("https://example.invalid", "test-only-secret")
        with patch.object(reader._opener, "open", side_effect=URLError("sensitive detail")):
            with self.assertRaises(IntegrationError) as error:
                reader.user("human")
        self.assertNotIn("sensitive detail", str(error.exception))


if __name__ == "__main__":
    unittest.main()


class ChannelPaginationTests(unittest.TestCase):
    def test_old_kickoff_is_reachable_past_first_page(self):
        reader = MattermostReader("http://localhost:8065", "test-only-secret")
        first = {str(i): {"id": str(i)} for i in range(200)}
        old = {"old": {"id": "old", "message": "INV_START old-run"}}
        with patch.object(reader, "_get", side_effect=[
            {"order": list(first), "posts": first},
            {"order": ["old"], "posts": old}, {"order": [], "posts": {}},
        ]) as get:
            result = reader.channel_posts("c" * 26)
        self.assertEqual(len(result["posts"]), 201)
        self.assertIn("old", result["posts"])
        self.assertIn("before=199", get.call_args_list[1].args[0])
        self.assertIn("before=old", get.call_args_list[2].args[0])

    def test_partial_or_nonadvancing_history_is_not_success(self):
        reader = MattermostReader("http://localhost:8065", "test-only-secret")
        page = {"order": ["a"], "posts": {"a": {"id": "a"}}}
        for replies in ([page, page], [page, IntegrationError("connection failed")], [{}]):
            with self.subTest(replies=len(replies)), patch.object(reader, "_get", side_effect=replies):
                with self.assertRaises(IntegrationError):
                    reader.channel_posts("c" * 26)
