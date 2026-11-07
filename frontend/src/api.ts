import type {
  Action, CollabMessage, Incident, Investigation, Me, Property, QueueRow, RequestRow, Staff, TimelineEvent,
} from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

type Json = Record<string, unknown>;

function detail(data: unknown, status: number): string {
  const value = (data as { detail?: unknown } | null)?.detail;
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return "Invalid input: " + value.map((e) => (e as { msg?: string }).msg).join("; ");
  return `Request failed (HTTP ${status})`;
}

/** Incremental Server-Sent Events parser; tolerates events split across network chunks. */
export function sseParser(onEvent: (event: { id?: string; event?: string; data: string }) => void) {
  let buffer = "";
  return (chunk: string) => {
    buffer = (buffer + chunk).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const parsed: { id?: string; event?: string; data: string } = { data: "" };
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (!line || line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "data") data.push(value);
        else if (field === "id") parsed.id = value;
        else if (field === "event") parsed.event = value;
      }
      if (data.length) onEvent({ ...parsed, data: data.join("\n") });
    }
  };
}

export function createApi(token: string, fetchImpl: typeof fetch = (...args) => fetch(...args), base = "/api") {
  const auth = { Authorization: `Bearer ${token}` };

  async function call<T>(method: string, path: string, body?: unknown, idempotent = false): Promise<T> {
    const headers: Record<string, string> = { ...auth };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    // A fresh key per user action; the backend replays or refuses duplicates.
    if (idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
    const response = await fetchImpl(base + path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!response.ok) throw new ApiError(response.status, detail(data, response.status));
    return data as T;
  }

  return {
    me: () => call<Me>("GET", "/me"),
    properties: () => call<Property[]>("GET", "/properties"),
    myRequests: () => call<RequestRow[]>("GET", "/requests?limit=100"),
    submit: (body: Json) => call<RequestRow>("POST", "/requests", body, true),
    queue: (status?: string) => call<QueueRow[]>("GET", "/queue" + (status ? `?status=${status}` : "")),
    acknowledge: (id: string) => call<RequestRow>("PUT", `/requests/${id}/acknowledgement`),
    investigations: (requestId: string) => call<Investigation[]>("GET", `/requests/${requestId}/investigations`),
    investigate: (requestId: string) => call<Investigation>("POST", `/requests/${requestId}/investigations`, undefined, true),
    retry: (runId: string) => call<Investigation>("POST", `/investigations/${runId}/retry`, undefined, true),
    brief: async (runId: string) => {
      const response = await fetchImpl(`${base}/investigations/${runId}/brief`, { headers: auth });
      if (!response.ok) throw new ApiError(response.status, `Brief unavailable (HTTP ${response.status})`);
      return response.text();
    },
    collaboration: (runId: string) => call<CollabMessage[]>("GET", `/investigations/${runId}/collaboration`),
    syncCollaboration: (runId: string) => call<CollabMessage[]>("POST", `/investigations/${runId}/collaboration/sync`, {}),
    actions: (requestId: string) => call<Action[]>("GET", `/requests/${requestId}/actions`),
    propose: (requestId: string, body: Json) => call<Action>("POST", `/requests/${requestId}/actions`, body, true),
    decide: (action: Action, decision: "approved" | "rejected", reason?: string) =>
      call<Action>("POST", `/actions/${action.id}/decision`, {
        decision, revision: action.revision, details_hash: action.details_hash, reason: reason || null,
      }),
    execute: (actionId: string) => call<Action>("POST", `/actions/${actionId}/execution`, undefined, true),
    timeline: (requestId: string) => call<TimelineEvent[]>("GET", `/requests/${requestId}/timeline`),
    incidents: () => call<Incident[]>("GET", "/incidents"),
    createIncident: (body: Json) => call<Incident>("POST", "/incidents", body, true),
    link: (incidentId: string, requestId: string) => call<Incident>("PUT", `/incidents/${incidentId}/requests/${requestId}`),
    unlink: (incidentId: string, requestId: string) => call<Incident>("DELETE", `/incidents/${incidentId}/requests/${requestId}`),
    assign: (incidentId: string, coordinatorId: string) =>
      call<Incident>("PUT", `/incidents/${incidentId}/coordinator`, { coordinator_id: coordinatorId }),
    staff: (propertyId: string) => call<Staff[]>("GET", `/properties/${propertyId}/staff`),

    /** Follow the live timeline until `signal` aborts, reconnecting from the last sequence seen. */
    async streamTimeline(requestId: string, onEvent: (event: TimelineEvent) => void,
                         signal: AbortSignal, onError: (message: string | null) => void) {
      let cursor = 0;
      while (!signal.aborted) {
        try {
          const response = await fetchImpl(`${base}/requests/${requestId}/timeline/stream?after=${cursor}&timeout=60`,
                                           { headers: auth, signal });
          if (!response.ok || !response.body) throw new ApiError(response.status, `Live timeline unavailable (HTTP ${response.status})`);
          onError(null);
          const parse = sseParser(({ data }) => {
            const event = JSON.parse(data) as TimelineEvent;
            cursor = Math.max(cursor, event.sequence);
            onEvent(event);
          });
          const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            parse(value);
          }
        } catch (error) {
          if (signal.aborted) return;
          onError(error instanceof Error ? error.message : "Live timeline disconnected");
          if (error instanceof ApiError && (error.status === 401 || error.status === 403 || error.status === 404)) return;
          await new Promise((resolve) => setTimeout(resolve, 3000));
        }
      }
    },
  };
}

export type Api = ReturnType<typeof createApi>;
