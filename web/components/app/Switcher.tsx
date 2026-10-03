"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";

interface Item {
  id: number;
  name: string;
}

interface Props {
  label: string;
  items: Item[];
  currentId: number | null;
  onSelect: (id: number) => void;
}

export function Switcher({ label, items, currentId, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const current = items.find((i) => i.id === currentId);

  return (
    <div className="switcher">
      <button className="switcher-btn" onClick={() => setOpen((o) => !o)}>
        <span className="switcher-meta">
          <span className="switcher-label">{label}</span>
          <span className="switcher-current">{current?.name ?? "—"}</span>
        </span>
        <Icon name="chevronDown" size={14} />
      </button>
      {open && (
        <div className="switcher-menu">
          {items.map((i) => (
            <button
              key={i.id}
              className={`switcher-item ${i.id === currentId ? "active" : ""}`}
              onClick={() => {
                onSelect(i.id);
                setOpen(false);
              }}
            >
              {i.name}
              {i.id === currentId && <Icon name="check" size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
