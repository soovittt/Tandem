"use client";

import type { Investigation } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Avatar, PriorityTag, Status } from "@/components/ui";

interface Props {
  investigations: Investigation[];
  onOpen: (id: string) => void;
}

export function InvestigationsView({ investigations, onOpen }: Props) {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Investigations</h1>
          <div className="page-sub">Every active problem, and where it stands.</div>
        </div>
        <button className="btn btn-primary"><Icon name="plus" size={15} /> New</button>
      </div>

      {investigations.length === 0 ? (
        <div className="dim">No investigations in this project yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Investigation</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Owner</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {investigations.map((inv) => (
              <tr key={inv.id} onClick={() => onOpen(inv.id)}>
                <td>
                  <div className="cell-title">{inv.title}</div>
                  <div className="cell-sub">{inv.summary}</div>
                </td>
                <td><Status status={inv.status} /></td>
                <td><PriorityTag priority={inv.priority} /></td>
                <td><span className="owner"><Avatar name={inv.owner} />{inv.owner}</span></td>
                <td className="dim">{inv.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
