import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiError, createApi } from "./api";
import { ManagerView } from "./ManagerView";
import { TenantView } from "./TenantView";
import type { Me } from "./types";

const STORAGE_KEY = "property-rescue-token";

function stored(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function App({ fetchImpl }: { fetchImpl?: typeof fetch }) {
  const [token, setToken] = useState(stored);
  const [draft, setDraft] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const api = useMemo(() => (token ? createApi(token, fetchImpl) : null), [token, fetchImpl]);

  useEffect(() => {
    if (!api) return;
    api.me().then(setMe).catch((e) => {
      setError(e instanceof ApiError && e.status === 401 ? "That token was not accepted." : "API unreachable; is it running on port 8100?");
      signOut();
    });
  }, [api]);

  function signIn(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try { sessionStorage.setItem(STORAGE_KEY, draft.trim()); } catch { /* session-only convenience */ }
    setToken(draft.trim());
    setDraft("");
  }

  function signOut() {
    try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
    setToken("");
    setMe(null);
  }

  if (!api || !me) {
    return (
      <form className="signin card" onSubmit={signIn} aria-label="Sign in">
        <h1>Property Rescue</h1>
        <p className="muted">Local demo sign-in. Paste one value from <code>.local/app/demo-tokens.json</code>
          (owner, coordinator, coordinator_two, member, tenant…). It stays in this browser tab only.</p>
        <label>Demo token <input type="password" value={draft} onChange={(e) => setDraft(e.target.value)} required autoComplete="off" /></label>
        <button type="submit">Sign in</button>
        {error && <p role="alert" className="error">{error}</p>}
      </form>
    );
  }

  return (
    <>
      <header className="top">
        <h1>Property Rescue</h1>
        <span className="muted">Fictional demo data · {me.name} ({me.role})</span>
        <button className="secondary" onClick={signOut}>Sign out</button>
      </header>
      {me.role === "tenant" ? <TenantView api={api} /> : <ManagerView api={api} me={me} />}
    </>
  );
}
