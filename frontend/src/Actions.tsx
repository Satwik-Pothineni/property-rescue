import { useState, type FormEvent } from "react";
import { ApiError, type Api } from "./api";
import type { Action, ActionKind, Investigation } from "./types";

const KIND_LABEL: Record<ActionKind, string> = {
  contact_vendor: "Contact vendor",
  schedule_visit: "Schedule visit",
  authorize_spend: "Authorize spending",
  close_request: "Close request",
};

function message(error: unknown): string {
  return error instanceof ApiError ? `${error.message} (HTTP ${error.status})` : "Network error; nothing was changed";
}

function describe(action: Action): string {
  const d = action.details;
  switch (action.kind) {
    case "contact_vendor": return String(d.message);
    case "schedule_visit": return `${new Date(String(d.window_start)).toLocaleString()} – ${new Date(String(d.window_end)).toLocaleString()}`;
    case "authorize_spend": return `${d.currency} ${d.amount}`;
    case "close_request": return String(d.resolution);
  }
}

export function ActionCard({ api, action, onChange }: { api: Api; action: Action; onChange: (a: Action) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(step: () => Promise<Action>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await step());
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  const decision = action.current_decision;
  return (
    <article className={`card action status-${action.status}`} aria-label={`${KIND_LABEL[action.kind]} action`}>
      <header>
        <strong>{KIND_LABEL[action.kind]}</strong>
        <span className="badge">{action.status}</span>
        <span className="muted">revision {action.revision}</span>
      </header>
      <p>{describe(action)}</p>
      <p className="muted">Why: {action.rationale} · Evidence: {action.evidence_ids.join(", ")}</p>
      {decision && (
        <p className="muted">
          {decision.decision} by {decision.authority} · expires {new Date(decision.expires_at).toLocaleString()}
          {decision.reason ? ` · “${decision.reason}”` : ""}
        </p>
      )}
      {action.result && (
        <p className="result">
          Result: {String(action.result.summary ?? action.result.error_code ?? action.result.request_status ?? "recorded")}
          {action.result.delivery === "not_sent" && <span className="badge warn">fictional – nothing sent</span>}
        </p>
      )}
      <div className="buttons">
        {action.status === "proposed" && (
          <>
            <button disabled={busy} onClick={() => run(() => api.decide(action, "approved"))}>Approve revision {action.revision}</button>
            <button disabled={busy} className="secondary" onClick={() => run(() => api.decide(action, "rejected"))}>Reject</button>
          </>
        )}
        {(action.status === "approved" || action.status === "failed") && (
          <button disabled={busy} onClick={() => run(() => api.execute(action.id))}>
            {action.status === "failed" ? "Retry execution" : "Execute"}
          </button>
        )}
      </div>
      {error && <p role="alert" className="error">Refused: {error}</p>}
    </article>
  );
}

export function ProposeForm({ api, requestId, investigation, onCreated }: {
  api: Api; requestId: string; investigation: Investigation; onCreated: (a: Action) => void;
}) {
  const evidence = Object.values(investigation.sections).flatMap((s) => s.evidence);
  const vendors = evidence.filter((e) => e.kind === "vendor");
  const [kind, setKind] = useState<ActionKind>("contact_vendor");
  const [vendorId, setVendorId] = useState(vendors[0]?.id.replace("vendor:", "") ?? "");
  const [text, setText] = useState("");
  const [amount, setAmount] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [rationale, setRationale] = useState("");
  const [cited, setCited] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  function details(): Record<string, unknown> {
    switch (kind) {
      case "contact_vendor": return { kind, vendor_id: vendorId, message: text };
      case "schedule_visit": return {
        kind, vendor_id: vendorId,
        window_start: start && new Date(start).toISOString(), window_end: end && new Date(end).toISOString(),
      };
      case "authorize_spend": return { kind, vendor_id: vendorId, amount, currency: "USD" };
      case "close_request": return { kind, resolution: text };
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      onCreated(await api.propose(requestId, {
        investigation_id: investigation.id, details: details(), rationale, evidence_ids: cited,
      }));
      setText(""); setRationale(""); setCited([]); setAmount("");
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <form className="card propose" onSubmit={submit} aria-label="Propose action">
      <strong>Propose an action</strong>
      <label>Kind
        <select value={kind} onChange={(e) => setKind(e.target.value as ActionKind)}>
          {Object.entries(KIND_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      {kind !== "close_request" && (
        <label>Vendor
          <select value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
            {vendors.map((v) => <option key={v.id} value={v.id.replace("vendor:", "")}>{String(v.record.name)}</option>)}
          </select>
        </label>
      )}
      {(kind === "contact_vendor" || kind === "close_request") && (
        <label>{kind === "contact_vendor" ? "Message to vendor" : "Resolution"}
          <textarea value={text} onChange={(e) => setText(e.target.value)} required maxLength={2000} />
        </label>
      )}
      {kind === "authorize_spend" && (
        <label>Amount (USD)
          <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </label>
      )}
      {kind === "schedule_visit" && (
        <div className="row">
          <label>From <input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} required /></label>
          <label>To <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required /></label>
        </div>
      )}
      <label>Rationale
        <input value={rationale} onChange={(e) => setRationale(e.target.value)} required maxLength={2000} />
      </label>
      <fieldset>
        <legend>Cite evidence</legend>
        {evidence.map((e) => (
          <label key={e.id} className="check">
            <input type="checkbox" checked={cited.includes(e.id)}
                   onChange={(ev) => setCited(ev.target.checked ? [...cited, e.id] : cited.filter((c) => c !== e.id))} />
            {e.id}
          </label>
        ))}
      </fieldset>
      <button type="submit">Submit proposal</button>
      {error && <p role="alert" className="error">Refused: {error}</p>}
    </form>
  );
}
