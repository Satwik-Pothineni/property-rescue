// Test double for the FastAPI backend: routes "METHOD /path" to canned responses and records calls.
export interface Call { method: string; path: string; headers: Record<string, string>; body: unknown }
type Reply = { status?: number; body?: unknown; text?: string };
type Route = Reply | ((call: Call) => Reply);

export function fakeBackend(routes: Record<string, Route>) {
  const calls: Call[] = [];
  const fetchImpl = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://test");
    const path = url.pathname.replace(/^\/api/, "") + url.search;
    const call: Call = {
      method: init.method ?? "GET", path, headers: (init.headers ?? {}) as Record<string, string>,
      body: init.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(call);
    const key = `${call.method} ${url.pathname.replace(/^\/api/, "")}`;
    const route = routes[key];
    if (!route) return new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
    const reply = typeof route === "function" ? route(call) : route;
    return new Response(reply.text ?? JSON.stringify(reply.body ?? null), { status: reply.status ?? 200 });
  };
  return { fetchImpl: fetchImpl as typeof fetch, calls };
}
