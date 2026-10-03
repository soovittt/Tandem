"use client";

import type { Investigation } from "@/lib/types";
import { AssistantPanel } from "@/components/investigation/AssistantPanel";
import { StatePanel } from "@/components/investigation/StatePanel";
import { Avatar, PriorityTag, Status } from "@/components/ui";

interface Props {
  investigation: Investigation;
  projectId: number | null;
  onBack: () => void;
}

export function InvestigationDetailView({ investigation, projectId, onBack }: Props) {
  return (
    <div className="detail">
      <div className="detail-top">
        <button className="detail-crumb" onClick={onBack}>← Investigations</button>
        <h1 className="detail-title">{investigation.title}</h1>
        <div className="meta-row">
          <Status status={investigation.status} />
          <span className="meta-sep" />
          <PriorityTag priority={investigation.priority} />
          <span className="meta-sep" />
          <span className="owner"><Avatar name={investigation.owner} />{investigation.owner}</span>
          <span className="meta-sep" />
          <span className="dim" style={{ fontSize: 12.5 }}>Updated {investigation.updated}</span>
        </div>
      </div>

      <div className="detail-body">
        <div className="detail-main">
          <StatePanel investigation={investigation} />
        </div>
        <div className="detail-aside">
          <AssistantPanel investigationTitle={investigation.title} projectId={projectId} />
        </div>
      </div>
    </div>
  );
}
