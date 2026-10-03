"use client";

import type { ReactNode } from "react";

// A small, curated set of line icons (Lucide-style). Crisp SVG, currentColor,
// so they inherit text color and never look like emoji clip-art.
const PATHS: Record<string, ReactNode> = {
  home: <path d="M3 10.2 12 4l9 6.2M5.5 9v11h13V9M10 20v-6h4v6" />,
  layers: <path d="M12 4 3 8.5l9 4.5 9-4.5L12 4ZM3 12.5l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5" />,
  bell: (
    <>
      <path d="M6 8a6 6 0 0 1 12 0c0 6 2.5 8 2.5 8h-17S6 14 6 8Z" />
      <path d="M10.2 21a2 2 0 0 0 3.6 0" />
    </>
  ),
  book: <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3.5H6.5A2.5 2.5 0 0 0 4 6v13.5ZM4 19.5V20a1 1 0 0 0 1 1h15" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  chevronRight: <path d="m9 5 7 7-7 7" />,
  chevronDown: <path d="m5 9 7 7 7-7" />,
  check: <path d="m20 6-11 11-5-5" />,
  x: <path d="M18 6 6 18M6 6l12 12" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  file: <path d="M14 3v5h5M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5ZM9 13h6M9 17h4" />,
  user: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
    </>
  ),
  chip: (
    <>
      <rect x="7" y="7" width="10" height="10" rx="1.5" />
      <path d="M10 3v3M14 3v3M10 18v3M14 18v3M3 10h3M3 14h3M18 10h3M18 14h3" />
    </>
  ),
  wrench: <path d="M15 6.5a3.5 3.5 0 0 0-4.9 4.4L3.5 17.5a2 2 0 1 0 3 3l6.6-6.6A3.5 3.5 0 0 0 17.5 9l-2.3 2.3-2.5-.7-.7-2.5L15 6.5Z" />,
  eye: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  chart: <path d="M4 4v16h16M8 16v-5M12.5 16V8M17 16v-3" />,
  edit: <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />,
  bulb: <path d="M9.5 18h5M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5.9 1.3.9 2.1h5.2c0-.8.3-1.6.9-2.1A6 6 0 0 0 12 3Z" />,
  beaker: <path d="M9.5 3h5M10.5 3v6L5.4 18a2 2 0 0 0 1.7 3h9.8a2 2 0 0 0 1.7-3L13.5 9V3M8 14h8" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  paperclip: <path d="M20.5 12.5 12 21a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.6 18.8a1.7 1.7 0 0 1-2.4-2.4L15 8.5" />,
  send: <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />,
  sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" />,
  sliders: (
    <>
      <path d="M4 8h9M17 8h3M4 16h3M11 16h9" />
      <circle cx="15" cy="8" r="2" />
      <circle cx="9" cy="16" r="2" />
    </>
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16h.01" />
    </>
  ),
  link: <path d="M10 13a4 4 0 0 0 5.6.4l3-3a4 4 0 0 0-5.7-5.7L11.2 6M14 11a4 4 0 0 0-5.6-.4l-3 3a4 4 0 0 0 5.7 5.7L12.8 18" />,
};

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {PATHS[name] ?? null}
    </svg>
  );
}

// Map domain kinds → icon names, used by timeline/entities/briefing.
export const KIND_ICON: Record<string, string> = {
  observation: "eye",
  result: "chart",
  decision: "check",
  procedure: "file",
  note: "edit",
  sample: "beaker",
  equipment: "chip",
  person: "user",
  approval: "bell",
  suggestion: "bulb",
};
