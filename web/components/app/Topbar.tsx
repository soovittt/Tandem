"use client";

import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({ crumb }: { crumb: string }) {
  return (
    <header className="topbar">
      <div className="crumb">
        <b>{crumb}</b>
      </div>
      <div className="topbar-actions">
        <ThemeToggle />
        <button className="btn-icon" title="Notifications"><Icon name="bell" size={16} /></button>
        <span className="avatar">SN</span>
      </div>
    </header>
  );
}
