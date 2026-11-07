import { describe, expect, it } from "vitest";
import { ApiError, createApi, sseParser } from "./api";
import { fakeBackend } from "./testing";
import type { TimelineEvent } from "./types";

describe("sseParser", () => {
  it("reassembles events split across chunks and CRLF line endings", () => {
    const seen: unknown[] = [];
    const feed = sseParser((e) => seen.push(e));
    feed("event: action.approved\r\nid: 4\r\ndata: {\"sequence\"");
    expect(seen).toEqual([]);
    feed(": 4}\r\n\r\nid: 5\ndata: line1\ndata: line2\n\n: keepalive\n\n");
    expect(seen).toEqual([
      { event: "action.approved", id: "4", data: "{\"sequence\": 4}" },
      { id: "5", data: "line1\nline2" },
    ]);
  });
});

describe("createApi", () => {
  it("sends the bearer token and a fresh idempotency key for consequential calls", async () => {
    const { fetchImpl, calls } = fakeBackend({ "POST /requests/r1/actions": { status: 201, body: { id: "a1" } } });
    const api = createApi("tok", fetchImpl);
    await api.propose("r1", { rationale: "x" });
    await api.propose("r1", { rationale: "x" });
    expect(calls[0].headers.Authorization).toBe("Bearer tok");
    expect(calls[0].headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(calls[1].headers["Idempotency-Key"]).not.toBe(calls[0].headers["Idempotency-Key"]);
  });

  it("surfaces the backend's refusal reason and status", async () => {
    const { fetchImpl } = fakeBackend({
      "POST /actions/a1/execution": { status: 409, body: { detail: "Approval expired; request a new decision" } },
      "GET /queue": { status: 502, text: "<html>bad gateway</html>" },
    });
    const api = createApi("tok", fetchImpl);
    await expect(api.execute("a1")).rejects.toEqual(new ApiError(409, "Approval expired; request a new decision"));
    await expect(api.queue()).rejects.toMatchObject({ status: 502, message: "Request failed (HTTP 502)" });
  });

  it("resumes the live timeline from the last sequence and stops when access is refused", async () => {
    let attempt = 0;
    const { fetchImpl, calls } = fakeBackend({
      "GET /requests/r1/timeline/stream": () => (++attempt === 1
        ? { text: 'id: 1\ndata: {"sequence": 1, "kind": "request.submitted"}\n\nid: 2\ndata: {"sequence": 2, "kind": "action.denied"}\n\n' }
        : { status: 403, body: { detail: "Management access required" } }),
    });
    const events: TimelineEvent[] = [];
    const errors: (string | null)[] = [];
    await createApi("tok", fetchImpl).streamTimeline("r1", (e) => events.push(e), new AbortController().signal, (m) => errors.push(m));
    expect(events.map((e) => e.sequence)).toEqual([1, 2]);
    expect(calls[1].path).toContain("after=2");
    expect(errors.at(-1)).toBe("Live timeline unavailable (HTTP 403)");
  });
});
