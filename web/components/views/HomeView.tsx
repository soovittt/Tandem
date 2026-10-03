"use client";

import { BRIEFING } from "@/lib/mock";
import type { Investigation, ViewKey } from "@/lib/types";
import { Icon, KIND_ICON } from "@/components/Icon";
import { Avatar, PriorityTag, Status } from "@/components/ui";

interface Props {
  investigations: Investigation[];
  onOpen: (id: string) => void;
  onGo: (v: ViewKey) => void;
}

export function HomeView({ investigations, onOpen, onGo }: Props) {
  const firstId = investigations[0]?.id;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Good morning</h1>
          <div className="page-sub">Here's what moved while you were away.</div>
        </div>
      </div>

      <div className="section">
        <div className="section-h">Needs your attention</div>
        <div className="inbox">
          {BRIEFING.map((b) => (
            <button
              key={b.id}
              className="inbox-row"
              onClick={() =>
                b.kind === "approval" ? onGo("approvals") : firstId ? onOpen(firstId) : onGo("investigations")
              }
            >
              <span className={`inbox-ic ${b.kind === "approval" ? "warn" : b.kind === "procedure" ? "neutral" : ""}`}>
                <Icon name={KIND_ICON[b.kind] ?? "sparkle"} size={16} />
              </span>
              <div>
                <div className="inbox-title">{b.title}</div>
                <div className="inbox-sub">{b.detail}</div>
              </div>
              <span className="chev"><Icon name="chevronRight" size={16} /></span>
            </button>
          ))}
        </div>
      </div>

      <div className="section">
        <div className="section-h">Active investigations</div>
        <div className="inv-cards">
          {investigations.map((inv) => (
            <button key={inv.id} className="inv-card" onClick={() => onOpen(inv.id)}>
              <div className="inv-card-top">
                <Status status={inv.status} />
                <PriorityTag priority={inv.priority} />
              </div>
              <div className="inv-card-title">{inv.title}</div>
              <div className="inv-card-sub">{inv.summary}</div>
              <div className="inv-card-foot">
                <Avatar name={inv.owner} /> {inv.owner} · {inv.updated}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
