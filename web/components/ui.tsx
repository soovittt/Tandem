"use client";

import type { InvestigationStatus, Priority } from "@/lib/types";
import { Icon, KIND_ICON } from "./Icon";

const STATUS_LABEL: Record<InvestigationStatus, string> = {
  active: "Active",
  awaiting: "Awaiting result",
  blocked: "Blocked",
  resolved: "Resolved",
};

export function Status({ status }: { status: InvestigationStatus }) {
  return (
    <span className="status">
      <span className={`status-dot dot-${status}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function PriorityTag({ priority }: { priority: Priority }) {
  return (
    <span className={`prio prio-${priority}`}>
      <span className="prio-bars"><i /><i /><i /></span>
      {priority}
    </span>
  );
}

export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <span className="conf">
      <span className="conf-track"><span className="conf-fill" style={{ width: `${pct}%` }} /></span>
      <span className="conf-pct">{pct}%</span>
    </span>
  );
}

export function Avatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return <span className="avatar">{initials}</span>;
}

export function EntityChip({ kind, label }: { kind: string; label: string }) {
  return (
    <span className="tag">
      <Icon name={KIND_ICON[kind] ?? "link"} size={13} />
      {label}
    </span>
  );
}
