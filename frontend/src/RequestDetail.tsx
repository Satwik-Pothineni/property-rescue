import { useCallback, useEffect, useState } from "react";
import { ApiError, type Api } from "./api";
import { ActionCard, ProposeForm } from "./Actions";
import type { Action, CollabMessage, Investigation, QueueRow, TimelineEvent } from "./types";

// Mention name of the Switch triage agent (e.g. pr-triage-claude for the Claude Code template).
const TRIAGE_AGENT = import.meta.env.VITE_TRIAGE_AGENT ?? "pr-triage";

function describeEvent(e: TimelineEvent): string {
  const d = e.details;
  const parts = [d.reason, d.step && `${d.step} ${d.status}`, !d.step && d.status, d.action_kind, d.title,
                 d.tag ?? (d.sender ? "message" : null), d.sender && `from ${d.sender}`];
  return parts.filter(Boolean).join(" · ");
}

export function RequestDetail({ api, row, onChanged }: { api: Api; row: QueueRow; onChanged: () => void }) {
  const request = row.request;
  const [runs, setRuns] = useState<Investigation[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [messages, setMessages] = useState<CollabMessage[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [live, setLive] = useState<string | null>("connecting…");
  const [notice, setNotice] = useState<string | null>(null);
  const [brief, setBrief] = useState<string | null>(null);
  const run = runs.at(-1);

  const report = (e: unknown) => setNotice(e instanceof ApiError ? `${e.message} (HTTP ${e.status})` : "Network error");

  const reload = useCallback(async () => {
    try {
      const [investigations, current] = await Promise.all([api.investigations(request.id), api.actions(request.id)]);
      setRuns(investigations);
      setActions(current);
      const latest = investigations.at(-1);
      if (latest) setMessages(await api.collaboration(latest.id));
    } catch (e) {
      report(e);
    }
  }, [api, request.id]);

  useEffect(() => {
    setEvents([]);
    setRuns([]);
    setActions([]);
    setMessages([]);
    setBrief(null);
    setNotice(null);
    void reload();
    const controller = new AbortController();
    let pending: ReturnType<typeof setTimeout> | undefined;
    void api.streamTimeline(request.id, (event) => {
      setEvents((all) => all.some((e) => e.sequence === event.sequence) ? all : [...all, event]);
      // Debounce: a burst of events (e.g. an investigation) triggers one refresh.
      clearTimeout(pending);
      pending = setTimeout(() => { void reload(); onChanged(); }, 300);
    }, controller.signal, setLive);
    return () => { controller.abort(); clearTimeout(pending); };
  }, [api, request.id, reload, onChanged]);

  async function attempt(step: () => Promise<unknown>) {
    setNotice(null);
    try {
      await step();
      await reload();
    } catch (e) {
      report(e);
    }
  }

  async function copyBrief() {
    if (!run) return;
    await attempt(async () => {
      const text = await api.brief(run.id);
      setBrief(text);
      try {
        await navigator.clipboard.writeText(text);
        setNotice("Brief copied. Paste it as one message in the private Switch investigation room.");
      } catch {
        setNotice("Copy the brief below and paste it in the private Switch investigation room.");
      }
    });
  }

  return (
    <section className="detail" aria-label="Request detail">
      <header>
        <h2>{request.title}</h2>
        <span className="badge">{request.status}</span>
        {row.incident && <span className="badge info">Incident: {row.incident.title} · coordinator {row.incident.coordinator.name}</span>}
      </header>
      <blockquote className="original">
        <span className="muted">Original complaint from {row.tenant_name} ({request.category}, {new Date(request.created_at).toLocaleString()}) — unchangeable</span>
        <p>{request.description}</p>
      </blockquote>
      {request.status === "submitted" && <button onClick={() => attempt(() => api.acknowledge(request.id))}>Acknowledge</button>}
      {notice && <p role="status" className="notice">{notice}</p>}

      <h3>Investigation</h3>
      <div className="buttons">
        <button onClick={() => attempt(async () => {
          const command = `@${TRIAGE_AGENT} investigate ${request.id}`;
          try {
            await navigator.clipboard.writeText(command);
            setNotice(`Copied “${command}”. Post it in the private Switch room; the agents fetch the evidence themselves.`);
          } catch {
            setNotice(`Post this in the private Switch room: ${command}`);
          }
        })}>Copy agent command</button>
        {!run && <button className="secondary" onClick={() => attempt(() => api.investigate(request.id))}>Collect evidence here</button>}
      </div>
      {run && (
        <div className="card">
          <p>
            Evidence: <span className="badge">{run.status}</span> · Agent review: <span className="badge">{run.agent_review.replaceAll("_", " ")}</span>
            <span className="muted"> · as of {run.as_of} · external actions: {run.external_actions}</span>
          </p>
          {run.status === "partial" && <button onClick={() => attempt(() => api.retry(run.id))}>Retry failed steps</button>}
          {Object.entries(run.sections).map(([name, section]) => (
            <details key={name} open={name === "vendors"}>
              <summary>{name} — {section.status}{section.attempt > 1 ? ` (attempt ${section.attempt})` : ""}</summary>
              <ul>
                {section.findings.map((f, i) => (
                  <li key={i}><span className={`badge kind-${f.kind}`}>{f.kind}</span> {f.text}
                    {f.sources.length > 0 && <span className="muted"> [{f.sources.join(", ")}]</span>}</li>
                ))}
              </ul>
            </details>
          ))}
          <div className="buttons">
            <button className="secondary" onClick={copyBrief}>Copy brief for Switch agents</button>
            <button className="secondary" onClick={() => attempt(async () => setMessages(await api.syncCollaboration(run.id)))}>
              Sync agent discussion from Mattermost
            </button>
          </div>
          {brief && <textarea className="brief" readOnly value={brief} aria-label="Investigation brief" />}
          {messages.length > 0 && (
            <div className="collab">
              <h4>Agent discussion (imported from Mattermost; agent text is unverified)</h4>
              {messages.map((m) => (
                <details key={m.post_id} open={m.tag === "INV_REPORT"}>
                  <summary>
                    <span className={`badge ${m.sender_is_bot ? "info" : ""}`}>{m.sender_is_bot ? "agent" : "human"}</span> {m.sender}
                    {m.tag && <code> {m.tag}</code>} <span className="muted">{new Date(m.posted_at).toLocaleTimeString()}{m.edited ? " · edited" : ""}</span>
                  </summary>
                  <pre>{m.message}</pre>
                </details>
              ))}
            </div>
          )}
        </div>
      )}

      <h3>Actions</h3>
      {actions.length === 0 && <p className="muted">No actions proposed.</p>}
      {actions.map((a) => (
        <ActionCard key={a.id} api={api} action={a}
                    onChange={(updated) => setActions((all) => all.map((x) => (x.id === updated.id ? updated : x)))} />
      ))}
      {run?.status === "ready_for_review" && request.status !== "closed" && (
        <ProposeForm api={api} requestId={request.id} investigation={run} onCreated={(a) => setActions((all) => [...all, a])} />
      )}

      <h3>Timeline <span className={`badge ${live ? "warn" : "ok"}`}>{live ? `offline: ${live}` : "live"}</span></h3>
      <ol className="timeline">
        {events.map((e) => (
          <li key={e.sequence} className={e.kind === "action.denied" || e.kind.endsWith("failed") ? "bad" : ""}>
            <span className="muted">#{e.sequence} {new Date(e.at).toLocaleTimeString()}</span> <code>{e.kind}</code>{" "}
            <span className="muted">{e.actor_role ?? "system"}</span> {describeEvent(e)}
          </li>
        ))}
      </ol>
    </section>
  );
}
