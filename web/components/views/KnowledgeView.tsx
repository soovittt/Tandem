"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { IntegrationRow } from "@/lib/types";
import { Icon } from "@/components/Icon";

export function KnowledgeView({ projectId }: { projectId: number | null }) {
  const [integrations, setIntegrations] = useState<IntegrationRow[]>([]);

  useEffect(() => {
    if (projectId == null) return;
    api.listIntegrations(projectId).then(setIntegrations).catch(() => setIntegrations([]));
  }, [projectId]);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Knowledge</h1>
          <div className="page-sub">The systems Tandem may read. Every claim it makes links back here.</div>
        </div>
        <button className="btn btn-primary"><Icon name="plus" size={15} /> Connect</button>
      </div>

      <div className="conns">
        {integrations.map((c) => (
          <div key={c.id} className="conn">
            <div className="conn-h">
              <span className="conn-name">{c.name}</span>
              <span className={`conn-badge ${c.status}`}>{c.status}</span>
            </div>
            <div className="dim" style={{ fontSize: 12.5, textTransform: "capitalize" }}>{c.kind}</div>
          </div>
        ))}
      </div>

      <div className="privacy-note">
        <Icon name="alert" size={16} />
        <span>
          Access is per-person and permissioned. Tandem reads only what you approve, keeps an
          inspectable audit trail, and runs on your private inference endpoint.
        </span>
      </div>
    </div>
  );
}
