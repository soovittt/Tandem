// The ONE place the frontend knows the backend. Everything goes through here.

import type {
  AuthUser,
  ChatResponse,
  IntegrationRow,
  Investigation,
  Org,
  Project,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- token storage ---
export function getToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("token") : null;
}
export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("token", token);
  else localStorage.removeItem("token");
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

// --- auth ---
export async function register(email: string, name: string, password: string, orgName: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password, org_name: orgName }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Sign-up failed");
  return res.json() as Promise<{ access_token: string }>;
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Incorrect email or password");
  return res.json() as Promise<{ access_token: string }>;
}

export const me = () => get<AuthUser>("/auth/me");

// --- workspace ---
export const listOrgs = () => get<Org[]>("/orgs");
export const listProjects = (orgId: number) => get<Project[]>(`/orgs/${orgId}/projects`);
export const listInvestigations = (projectId: number) =>
  get<Investigation[]>(`/projects/${projectId}/investigations`);
export const getInvestigation = (id: string) => get<Investigation>(`/investigations/${id}`);
export const listIntegrations = (projectId: number) =>
  get<IntegrationRow[]>(`/projects/${projectId}/integrations`);

// --- assistant ---
export async function sendChat(
  message: string,
  sessionId: string | null,
  images?: string[],
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message, session_id: sessionId, images }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
  return res.json();
}

/** Project-scoped assistant: uses that project's isolated memory + integrations. */
export async function sendProjectChat(
  projectId: number,
  message: string,
  sessionId: string | null,
  images?: string[],
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message, session_id: sessionId, images }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
  return res.json();
}
