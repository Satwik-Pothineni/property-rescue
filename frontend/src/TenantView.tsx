import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, type Api } from "./api";
import type { Property, RequestRow } from "./types";

export function TenantView({ api }: { api: Api }) {
  const [properties, setProperties] = useState<Property[]>([]);
  const [requests, setRequests] = useState<RequestRow[]>([]);
  const [propertyId, setPropertyId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("plumbing");
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [homes, mine] = await Promise.all([api.properties(), api.myRequests()]);
    setProperties(homes);
    setRequests(mine);
    setPropertyId((p) => p || homes[0]?.id || "");
  }, [api]);

  useEffect(() => { load().catch(() => setNotice("Could not load your requests")); }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await api.submit({ property_id: propertyId, title, description, category });
      setTitle(""); setDescription("");
      setNotice("Request sent to your landlord.");
      await load();
    } catch (e) {
      setNotice(e instanceof ApiError ? `Not sent: ${e.message}` : "Not sent: network error");
    }
  }

  return (
    <div className="layout">
      <aside>
        <form className="card" onSubmit={submit} aria-label="Report a problem">
          <h2>Report a problem</h2>
          <label>Home
            <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
              {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>Category
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {["plumbing", "electrical", "heating", "general"].map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
          <label>Short title <input value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} /></label>
          <label>What is happening?
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} required maxLength={5000} />
          </label>
          <button type="submit">Send request</button>
          {notice && <p role="status" className="notice">{notice}</p>}
        </form>
      </aside>
      <main>
        <h2>Your requests</h2>
        <ul className="queue">
          {requests.map((r) => (
            <li key={r.id}><strong>{r.title}</strong> <span className="badge">{r.status}</span>
              <span className="muted"> {new Date(r.created_at).toLocaleString()}</span></li>
          ))}
          {requests.length === 0 && <li className="muted">No requests yet.</li>}
        </ul>
      </main>
    </div>
  );
}
