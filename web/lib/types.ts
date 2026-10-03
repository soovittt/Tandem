// Shared types for the Tandem enterprise app.

// --- Assistant / chat (mirrors the Python API) ---
export interface Source {
  title: string;
  url: string;
}
export interface ChatResponse {
  session_id: string;
  text: string;
  steps: number;
  sources: Source[];
}
export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  images?: string[];
  sources?: Source[];
}

// --- The domain: an Investigation is the unit of technical work ---
export type InvestigationStatus = "active" | "awaiting" | "blocked" | "resolved";
export type Priority = "high" | "medium" | "low";

export interface Hypothesis {
  id: string;
  text: string;
  confidence: number; // 0..1
  status: "leading" | "considered" | "ruled-out";
}

export interface TimelineEvent {
  id: string;
  when: string; // human label, e.g. "2 days ago"
  kind: "observation" | "result" | "decision" | "procedure" | "note";
  text: string;
}

export interface Evidence {
  id: string;
  title: string;
  source: string; // system it came from, e.g. "Benchling", "XRD export"
  url: string;
}

export interface Entity {
  id: string;
  kind: "sample" | "equipment" | "procedure" | "person";
  label: string;
}

export interface Investigation {
  id: string;
  title: string;
  status: InvestigationStatus;
  priority: Priority;
  owner: string;
  updated: string;
  summary: string;
  hypotheses: Hypothesis[];
  timeline: TimelineEvent[];
  evidence: Evidence[];
  nextSteps: string[];
  entities: Entity[];
}

// --- Governance surfaces ---
export interface Approval {
  id: string;
  title: string;
  detail: string;
  investigation: string;
  requestedAt: string;
}

export type BriefingKind = "result" | "approval" | "procedure" | "suggestion";
export interface BriefingItem {
  id: string;
  kind: BriefingKind;
  title: string;
  detail: string;
  investigationId?: string;
}

export type ViewKey = "home" | "investigations" | "approvals" | "knowledge";

// --- platform (auth + workspace) ---
export interface AuthUser {
  id: number;
  email: string;
  name: string;
}
export interface Org {
  id: number;
  name: string;
  slug: string;
  role: string;
}
export interface Project {
  id: number;
  org_id: number;
  name: string;
  key: string;
  description: string;
}
export interface IntegrationRow {
  id: number;
  project_id: number;
  kind: string;
  name: string;
  status: string;
}
