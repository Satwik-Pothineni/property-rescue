import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createApi } from "./api";
import { ActionCard, ProposeForm } from "./Actions";
import { fakeBackend } from "./testing";
import type { Action, Investigation } from "./types";

const action: Action = {
  id: "a1", request_id: "r1", investigation_id: "i1", kind: "contact_vendor",
  details: { kind: "contact_vendor", vendor_id: "v1", message: "Please quote the tap repair." },
  rationale: "Vendor listed for plumbing", evidence_ids: ["vendor:v1"], revision: 2, details_hash: "h".repeat(64),
  status: "proposed", proposed_by: "u1", result: null, current_decision: null,
};

describe("ActionCard", () => {
  it("approves exactly the revision and hash the reviewer saw", async () => {
    const approved = { ...action, status: "approved", current_decision: {
      decision: "approved", decided_by: "u1", authority: "owner", reason: null,
      decided_at: "2026-11-06T12:00:00Z", expires_at: "2026-11-07T12:00:00Z" } } as Action;
    const { fetchImpl, calls } = fakeBackend({ "POST /actions/a1/decision": { body: approved } });
    const onChange = vi.fn();
    render(<ActionCard api={createApi("t", fetchImpl)} action={action} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Approve revision 2" }));
    expect(calls[0].body).toEqual({ decision: "approved", revision: 2, details_hash: "h".repeat(64), reason: null });
    expect(onChange).toHaveBeenCalledWith(approved);
  });

  it("shows the backend refusal and never reports a refused execution as done", async () => {
    const { fetchImpl } = fakeBackend({
      "POST /actions/a1/execution": { status: 409, body: { detail: "Approver no longer holds authority" } },
    });
    const onChange = vi.fn();
    render(<ActionCard api={createApi("t", fetchImpl)} action={{ ...action, status: "approved" }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Execute" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Refused: Approver no longer holds authority (HTTP 409)");
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("approved")).toBeTruthy();
  });

  it("labels fictional execution results as not sent", () => {
    render(<ActionCard api={createApi("t", fakeBackend({}).fetchImpl)} onChange={() => {}} action={{
      ...action, status: "executed", result: { mode: "fictional_demo", delivery: "not_sent", summary: "Recorded" } }} />);
    expect(screen.getByText("fictional – nothing sent")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ProposeForm", () => {
  const investigation: Investigation = {
    id: "i1", request_id: "r1", status: "ready_for_review", as_of: "2026-11-06", agent_review: "not_verified",
    external_actions: "none", sections: { vendors: { status: "succeeded", attempt: 1, findings: [], evidence: [
      { id: "vendor:v1", kind: "vendor", record: { name: "Fictional Harbor Plumbing" } },
      { id: "estimate:e1", kind: "estimate", record: {} }] } },
  };

  it("submits the chosen vendor, cited evidence and amount; shows validation refusals", async () => {
    const { fetchImpl, calls } = fakeBackend({
      "POST /requests/r1/actions": (call) => ((call.body as { details: { amount: string } }).details.amount === "abc"
        ? { status: 422, body: { detail: [{ msg: "Input should be a valid decimal" }] } }
        : { status: 201, body: { ...action, kind: "authorize_spend" } }),
    });
    const onCreated = vi.fn();
    render(<ProposeForm api={createApi("t", fetchImpl)} requestId="r1" investigation={investigation} onCreated={onCreated} />);
    await userEvent.selectOptions(screen.getByLabelText("Kind"), "authorize_spend");
    await userEvent.type(screen.getByLabelText("Amount (USD)"), "abc");
    await userEvent.type(screen.getByLabelText("Rationale"), "Within planning range");
    await userEvent.click(screen.getByLabelText("estimate:e1"));
    await userEvent.click(screen.getByRole("button", { name: "Submit proposal" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Invalid input: Input should be a valid decimal");
    expect(onCreated).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText("Amount (USD)"));
    await userEvent.type(screen.getByLabelText("Amount (USD)"), "220.00");
    await userEvent.click(screen.getByRole("button", { name: "Submit proposal" }));
    expect(calls.at(-1)?.body).toEqual({ investigation_id: "i1", rationale: "Within planning range", evidence_ids: ["estimate:e1"],
      details: { kind: "authorize_spend", vendor_id: "v1", amount: "220.00", currency: "USD" } });
    expect(onCreated).toHaveBeenCalled();
  });
});
