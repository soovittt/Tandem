"use client";

import type { AuthUser, Org, Project, ViewKey } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Avatar } from "@/components/ui";
import { Switcher } from "./Switcher";

const NAV: { key: ViewKey; label: string; icon: string }[] = [
  { key: "home", label: "Home", icon: "home" },
  { key: "investigations", label: "Investigations", icon: "layers" },
  { key: "approvals", label: "Approvals", icon: "bell" },
  { key: "knowledge", label: "Knowledge", icon: "book" },
];

interface Props {
  view: ViewKey;
  onNavigate: (v: ViewKey) => void;
  approvalsCount: number;
  orgs: Org[];
  orgId: number | null;
  onSelectOrg: (id: number) => void;
  projects: Project[];
  projectId: number | null;
  onSelectProject: (id: number) => void;
  user: AuthUser | null;
  onLogout: () => void;
}

export function Sidebar(props: Props) {
  return (
    <aside className="nav">
      <Switcher label="Organization" items={props.orgs} currentId={props.orgId} onSelect={props.onSelectOrg} />
      <Switcher label="Project" items={props.projects} currentId={props.projectId} onSelect={props.onSelectProject} />

      <div className="nav-search">
        <Icon name="search" size={15} /> Search <kbd>⌘K</kbd>
      </div>

      <div className="nav-group-label">Workspace</div>
      {NAV.map((item) => (
        <button
          key={item.key}
          className={`nav-item ${props.view === item.key ? "is-active" : ""}`}
          onClick={() => props.onNavigate(item.key)}
        >
          <Icon name={item.icon} size={16} />
          {item.label}
          {item.key === "approvals" && props.approvalsCount > 0 && (
            <span className="nav-item-badge">{props.approvalsCount}</span>
          )}
        </button>
      ))}

      <div className="nav-user">
        <Avatar name={props.user?.name ?? "?"} />
        <div className="nav-user-meta">
          <div className="nav-user-name">{props.user?.name}</div>
          <div className="dim" style={{ fontSize: 11 }}>{props.user?.email}</div>
        </div>
        <button className="btn-icon" title="Sign out" onClick={props.onLogout}>
          <Icon name="x" size={15} />
        </button>
      </div>
    </aside>
  );
}
