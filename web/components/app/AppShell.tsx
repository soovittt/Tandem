"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Investigation, Org, Project, ViewKey } from "@/lib/types";
import { HomeView } from "@/components/views/HomeView";
import { InvestigationsView } from "@/components/views/InvestigationsView";
import { InvestigationDetailView } from "@/components/views/InvestigationDetailView";
import { ApprovalsView } from "@/components/views/ApprovalsView";
import { KnowledgeView } from "@/components/views/KnowledgeView";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

const TITLES: Record<ViewKey, string> = {
  home: "Home",
  investigations: "Investigations",
  approvals: "Approvals",
  knowledge: "Knowledge",
};

export function AppShell() {
  const { user, logout } = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState<number | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [view, setView] = useState<ViewKey>("home");
  const [activeId, setActiveId] = useState<string | null>(null);

  // Load chain: orgs → projects (for current org) → investigations (for current project).
  useEffect(() => {
    api.listOrgs().then((o) => {
      setOrgs(o);
      if (o[0]) setOrgId(o[0].id);
    });
  }, []);
  useEffect(() => {
    if (orgId == null) return;
    api.listProjects(orgId).then((p) => {
      setProjects(p);
      setProjectId(p[0]?.id ?? null);
    });
  }, [orgId]);
  useEffect(() => {
    if (projectId == null) {
      setInvestigations([]);
      return;
    }
    api.listInvestigations(projectId).then(setInvestigations).catch(() => setInvestigations([]));
  }, [projectId]);

  const go = (v: ViewKey) => {
    setActiveId(null);
    setView(v);
  };
  const openInvestigation = (id: string) => {
    setActiveId(id);
    setView("investigations");
  };

  const active = investigations.find((i) => i.id === activeId) ?? null;
  const crumb = active ? active.title : TITLES[view];

  return (
    <div className="app">
      <Sidebar
        view={view}
        onNavigate={go}
        approvalsCount={2}
        orgs={orgs}
        orgId={orgId}
        onSelectOrg={setOrgId}
        projects={projects}
        projectId={projectId}
        onSelectProject={setProjectId}
        user={user}
        onLogout={logout}
      />
      <div className="workspace">
        <Topbar crumb={crumb} />
        <div className="surface">
          {view === "home" && <HomeView investigations={investigations} onOpen={openInvestigation} onGo={go} />}
          {view === "investigations" && !active && (
            <InvestigationsView investigations={investigations} onOpen={openInvestigation} />
          )}
          {view === "investigations" && active && (
            <InvestigationDetailView
              investigation={active}
              projectId={projectId}
              onBack={() => setActiveId(null)}
            />
          )}
          {view === "approvals" && <ApprovalsView />}
          {view === "knowledge" && <KnowledgeView projectId={projectId} />}
        </div>
      </div>
    </div>
  );
}
