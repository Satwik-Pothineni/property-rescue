import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, type Api } from "./api";
import { RequestDetail } from "./RequestDetail";
import type { Incident, Me, QueueRow, Staff } from "./types";

function errorText(e: unknown) {
  return e instanceof ApiError ? `${e.message} (HTTP ${e.status})` : "Network error; nothing was changed";
}

export function ManagerView({ api, me }: { api: Api; me: Me }) {
  const [rows, setRows] = useState<QueueRow[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [queue, groups] = await Promise.all([api.queue(status || undefined), api.incidents()]);
      setRows(queue);
      setIncidents(groups);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [api, status]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 10000);
    return () => clearInterval(timer);
  }, [refresh]);

  const selected = rows.find((r) => r.request.id === selectedId);
  const teamMode = rows.some((r) => r.property.team_id) || incidents.length > 0;
  const toggle = (id: string) => setChecked((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const chosen = rows.filter((r) => checked.includes(r.request.id));

  async function change(step: () => Promise<unknown>) {
    setError(null);
    try {
      await step();
      setChecked([]);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="layout">
      <aside>
        <div className="row">
          <h2>{teamMode ? "Team operations queue" : "Your properties' requests"}</h2>
          <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="submitted">Submitted</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        {error && <p role="alert" className="error">{error}</p>}
        <ul className="queue">
          {rows.map((r) => (
            <li key={r.request.id} className={r.request.id === selectedId ? "selected" : ""}>
              {r.property.team_id && (
                <input type="checkbox" aria-label={`Select ${r.request.title}`} checked={checked.includes(r.request.id)}
                       onChange={() => toggle(r.request.id)} />
              )}
              <button className="link" onClick={() => setSelectedId(r.request.id)}>
                <strong>{r.request.title}</strong>
                <span className="muted">{r.property.name} · {r.tenant_name} · {r.request.status}</span>
                <span>
                  {r.incident && <span className="badge info">{r.incident.title}</span>}
                  {r.investigation && <span className="badge">evidence {r.investigation.status}</span>}
                  {Object.entries(r.actions).map(([state, n]) => <span key={state} className="badge">{n} {state}</span>)}
                </span>
              </button>
            </li>
          ))}
          {rows.length === 0 && <li className="muted">No requests.</li>}
        </ul>
        {teamMode && <Incidents api={api} me={me} incidents={incidents} chosen={chosen} change={change} />}
      </aside>
      <main>
        {selected ? <RequestDetail api={api} row={selected} onChanged={refresh} />
                  : <p className="muted">Select a request to see its evidence, actions and live timeline.</p>}
      </main>
    </div>
  );
}

function Incidents({ api, incidents, chosen, change }: {
  api: Api; me: Me; incidents: Incident[]; chosen: QueueRow[]; change: (step: () => Promise<unknown>) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [coordinator, setCoordinator] = useState("");
  const properties = useMemo(() => [...new Set(chosen.map((r) => r.property.id))], [chosen]);
  const property = properties.length === 1 ? properties[0] : null;
  const firstIncidentProperty = incidents[0]?.property_id;

  useEffect(() => {
    const target = property ?? firstIncidentProperty;
    if (!target) return;
    api.staff(target).then((people) => {
      setStaff(people);
      setCoordinator((c) => c || people.find((p) => p.role === "coordinator")?.id || "");
    }).catch(() => setStaff([]));
  }, [api, property, firstIncidentProperty]);

  const coordinators = staff.filter((s) => s.role === "coordinator" && s.active);
  return (
    <section aria-label="Incidents">
      <h2>Incidents</h2>
      <div className="card">
        <strong>Group {chosen.length} selected request{chosen.length === 1 ? "" : "s"}</strong>
        {properties.length > 1 && <p className="error">Selected requests must be on one property.</p>}
        <input placeholder="Incident title" aria-label="Incident title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <select aria-label="Coordinator" value={coordinator} onChange={(e) => setCoordinator(e.target.value)}>
          {coordinators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <button disabled={!property || !title.trim() || !coordinator}
                onClick={() => change(() => api.createIncident({
                  property_id: property, title: title.trim(), coordinator_id: coordinator,
                  request_ids: chosen.map((r) => r.request.id),
                }).then(() => setTitle("")))}>
          Create incident
        </button>
      </div>
      {incidents.map((incident) => (
        <div key={incident.id} className="card">
          <strong>{incident.title}</strong> <span className="muted">{incident.property_name}</span>
          <label>Coordinator
            <select aria-label={`Coordinator for ${incident.title}`} value={incident.coordinator.id}
                    onChange={(e) => change(() => api.assign(incident.id, e.target.value))}>
              {!coordinators.some((c) => c.id === incident.coordinator.id) &&
                <option value={incident.coordinator.id}>{incident.coordinator.name}</option>}
              {coordinators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <ul>
            {incident.requests.map((r) => (
              <li key={r.id}>{r.title} <span className="muted">({r.status})</span>{" "}
                <button className="link" onClick={() => change(() => api.unlink(incident.id, r.id))}>unlink</button></li>
            ))}
          </ul>
          {chosen.length > 0 && (
            <button className="secondary" onClick={() => change(async () => {
              for (const r of chosen) await api.link(incident.id, r.request.id);
            })}>Add selected to this incident</button>
          )}
        </div>
      ))}
    </section>
  );
}
