"use client";

import { useState } from "react";
import { APPROVALS } from "@/lib/mock";
import { Icon } from "@/components/Icon";

type Decision = "pending" | "approved" | "denied";

export function ApprovalsView() {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const decide = (id: string, d: Decision) => setDecisions((p) => ({ ...p, [id]: d }));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Approvals</h1>
          <div className="page-sub">Consequential actions wait here for your sign-off — nothing runs without it.</div>
        </div>
      </div>

      <div className="appr">
        {APPROVALS.map((a) => {
          const st = decisions[a.id] ?? "pending";
          return (
            <div key={a.id} className={`appr-item ${st !== "pending" ? st : ""}`}>
              <div className="appr-body">
                <div className="appr-title">{a.title}</div>
                <div className="dim" style={{ fontSize: 12.5 }}>{a.detail}</div>
                <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>{a.investigation} · {a.requestedAt}</div>
              </div>
              {st === "pending" ? (
                <div className="appr-actions">
                  <button className="btn btn-primary btn-sm" onClick={() => decide(a.id, "approved")}>
                    <Icon name="check" size={14} /> Approve
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => decide(a.id, "denied")}>Decline</button>
                </div>
              ) : (
                <div className={`appr-result ${st === "approved" ? "ok" : "no"}`}>
                  <Icon name={st === "approved" ? "check" : "x"} size={14} />
                  {st === "approved" ? "Approved" : "Declined"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
