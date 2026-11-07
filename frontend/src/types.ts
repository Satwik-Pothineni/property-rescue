// Mirrors the FastAPI responses. The backend is authoritative for every permission.

export type Role = "tenant" | "owner" | "staff";
export type ActionKind = "contact_vendor" | "schedule_visit" | "authorize_spend" | "close_request";
export type ActionStatus = "proposed" | "approved" | "rejected" | "executing" | "executed" | "failed";

export interface Me { id: string; name: string; role: Role }

export interface Property { id: string; name: string; address: string; owner_id: string; team_id: string | null }

export interface RequestRow {
  id: string; property_id: string; tenant_id: string; incident_id: string | null;
  title: string; description: string; category: string; status: string; created_at: string;
}

export interface QueueRow {
  request: RequestRow;
  tenant_name: string;
  property: { id: string; name: string; team_id: string | null };
  incident: { id: string; title: string; coordinator: { id: string; name: string } } | null;
  investigation: { id: string; status: string } | null;
  actions: Partial<Record<ActionStatus, number>>;
}

export interface Finding { kind: "observation" | "uncertain" | "missing" | "proposal"; text: string; sources: string[] }
export interface Evidence { id: string; kind: string; record: Record<string, unknown> }
export interface Section { status: "succeeded" | "failed"; attempt: number; evidence: Evidence[]; findings: Finding[] }

export interface Investigation {
  id: string; request_id: string; status: "collecting" | "ready_for_review" | "partial"; as_of: string;
  sections: Record<string, Section>; agent_review: string; external_actions: string;
}

export interface Decision {
  decision: "approved" | "rejected"; decided_by: string; authority: string;
  reason: string | null; decided_at: string; expires_at: string;
}

export interface Action {
  id: string; request_id: string; investigation_id: string; kind: ActionKind;
  details: Record<string, unknown>; rationale: string; evidence_ids: string[];
  revision: number; details_hash: string; status: ActionStatus; proposed_by: string;
  result: Record<string, unknown> | null; current_decision: Decision | null;
}

export interface TimelineEvent {
  sequence: number; kind: string; at: string; actor_id: string | null; actor_role: string | null;
  action_id: string | null; details: Record<string, unknown>;
}

export interface Incident {
  id: string; property_id: string; team_id: string; property_name: string; title: string; status: string;
  coordinator: { id: string; name: string }; requests: RequestRow[];
}

export interface CollabMessage {
  post_id: string; sender: string; sender_is_bot: boolean; tag: string | null;
  message: string; edited: boolean; posted_at: string;
}

export interface Staff { id: string; name: string; role: "coordinator" | "member"; active: boolean }
