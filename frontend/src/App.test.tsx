import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { fakeBackend } from "./testing";

const request = (id: string, title: string, team = true) => ({
  request: { id, property_id: team ? "p-team" : "p-home", tenant_id: "t1", incident_id: null, title,
             description: "Fictional", category: "plumbing", status: "submitted", created_at: "2026-11-06T12:00:00Z" },
  tenant_name: "Alex Demo", property: { id: team ? "p-team" : "p-home", name: "Apartments", team_id: team ? "team" : null },
  incident: null, investigation: null, actions: {},
});

async function signIn() {
  await userEvent.type(screen.getByLabelText("Demo token"), "x".repeat(40));
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("App", () => {
  beforeEach(() => sessionStorage.clear());

  it("rejects an unknown token without showing any data", async () => {
    const { fetchImpl } = fakeBackend({ "GET /me": { status: 401, body: { detail: "Invalid credentials" } } });
    render(<App fetchImpl={fetchImpl} />);
    await signIn();
    expect((await screen.findByRole("alert")).textContent).toContain("That token was not accepted.");
    expect(sessionStorage.getItem("property-rescue-token")).toBeNull();
  });

  it("gives tenants a request form and no management controls", async () => {
    const { fetchImpl, calls } = fakeBackend({
      "GET /me": { body: { id: "t1", name: "Alex Demo", role: "tenant" } },
      "GET /properties": { body: [{ id: "p-home", name: "Fictional Cottage", address: "x", owner_id: "o", team_id: null }] },
      "GET /requests": { body: [] },
      "POST /requests": { status: 201, body: {} },
    });
    render(<App fetchImpl={fetchImpl} />);
    await signIn();
    await userEvent.type(await screen.findByLabelText("Short title"), "Tap drips");
    await userEvent.type(screen.getByLabelText("What is happening?"), "Cold tap drips overnight");
    await userEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText("Request sent to your landlord.")).toBeTruthy();
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.body).toEqual({ property_id: "p-home", title: "Tap drips", description: "Cold tap drips overnight", category: "plumbing" });
    expect(post.headers["Idempotency-Key"]).toBeTruthy();
    expect(screen.queryByText(/queue/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });

  it("lets a coordinator group selected queue requests into an incident and shows refusals", async () => {
    let attempts = 0;
    const { fetchImpl, calls } = fakeBackend({
      "GET /me": { body: { id: "c1", name: "Robin Demo", role: "staff" } },
      "GET /queue": { body: [request("r1", "No hot water"), request("r2", "Radiator cold")] },
      "GET /incidents": { body: [] },
      "GET /properties/p-team/staff": { body: [{ id: "c2", name: "Riley Demo", role: "coordinator", active: true },
                                               { id: "m1", name: "Drew Demo", role: "member", active: true }] },
      "POST /incidents": () => (++attempts === 1
        ? { status: 409, body: { detail: "Request is linked to another incident; unlink it first" } }
        : { status: 201, body: {} }),
    });
    render(<App fetchImpl={fetchImpl} />);
    await signIn();
    await userEvent.click(await screen.findByLabelText("Select No hot water"));
    await userEvent.click(screen.getByLabelText("Select Radiator cold"));
    await userEvent.type(screen.getByLabelText("Incident title"), "Boiler outage");
    expect((screen.getByLabelText("Coordinator") as HTMLSelectElement).selectedOptions[0].textContent).toBe("Riley Demo");
    await userEvent.click(screen.getByRole("button", { name: "Create incident" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Request is linked to another incident; unlink it first (HTTP 409)");
    await userEvent.click(screen.getByRole("button", { name: "Create incident" }));
    const created = calls.filter((c) => c.method === "POST" && c.path === "/incidents");
    expect(created).toHaveLength(2);
    expect(created[1].body).toEqual({ property_id: "p-team", title: "Boiler outage", coordinator_id: "c2", request_ids: ["r1", "r2"] });
  });
});
