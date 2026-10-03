// Domain-specific sample data so the enterprise UI feels real without needing
// the full backend yet. (These become real API calls later — same shapes.)

import type { Approval, BriefingItem, Investigation } from "./types";

export const INVESTIGATIONS: Investigation[] = [
  {
    id: "inv-antml",
    title: "Uneven cathode coating — Line 3",
    status: "awaiting",
    priority: "high",
    owner: "You",
    updated: "20 min ago",
    summary:
      "Battery electrodes from Line 3 show uneven coating thickness. Two candidate causes; awaiting a DSC result to distinguish them.",
    hypotheses: [
      { id: "h1", text: "Slurry viscosity drift (binder lot change)", confidence: 0.55, status: "leading" },
      { id: "h2", text: "Coating oven running ~10°C hot", confidence: 0.3, status: "considered" },
      { id: "h3", text: "Comma-bar gap misaligned", confidence: 0.15, status: "ruled-out" },
    ],
    timeline: [
      { id: "t1", when: "3 days ago", kind: "observation", text: "Photo of uneven coating on sample A-7 uploaded." },
      { id: "t2", when: "3 days ago", kind: "note", text: "Similar appearance last month had two different root causes." },
      { id: "t3", when: "2 days ago", kind: "procedure", text: "SOP-114 (mixing) was revised — new rest time." },
      { id: "t4", when: "20 min ago", kind: "result", text: "DSC result for A-7 arrived — under review." },
    ],
    evidence: [
      { id: "e1", title: "Sample A-7 coating photo", source: "Mobile capture", url: "#" },
      { id: "e2", title: "XRD export — batch 0912", source: "Instrument export", url: "#" },
      { id: "e3", title: "SOP-114 rev C", source: "Benchling", url: "#" },
    ],
    nextSteps: [
      "Compare DSC of A-7 vs a good electrode to confirm binder hypothesis.",
      "Pull last 5 viscosity readings for the new binder lot.",
    ],
    entities: [
      { id: "en1", kind: "sample", label: "A-7" },
      { id: "en2", kind: "equipment", label: "Coating line 3" },
      { id: "en3", kind: "procedure", label: "SOP-114" },
      { id: "en4", kind: "person", label: "M. Ortiz (night shift)" },
    ],
  },
  {
    id: "inv-cap",
    title: "Capacity fade after 200 cycles",
    status: "active",
    priority: "medium",
    owner: "R. Chen",
    updated: "yesterday",
    summary: "Cells lose ~8% capacity by cycle 200 vs the 3% target. Investigating electrolyte formulation.",
    hypotheses: [
      { id: "h1", text: "SEI growth from additive shortfall", confidence: 0.6, status: "leading" },
      { id: "h2", text: "Cathode cracking at high C-rate", confidence: 0.35, status: "considered" },
    ],
    timeline: [
      { id: "t1", when: "1 week ago", kind: "observation", text: "Cycle-life test flagged fade at cycle 180." },
      { id: "t2", when: "3 days ago", kind: "decision", text: "Decided to pull cells for post-mortem EIS." },
    ],
    evidence: [{ id: "e1", title: "Cycler log — cell group C", source: "Instrument export", url: "#" }],
    nextSteps: ["Run EIS on 3 aged cells.", "Check additive lot certificate."],
    entities: [
      { id: "en1", kind: "equipment", label: "Cycler bay 2" },
      { id: "en2", kind: "person", label: "R. Chen" },
    ],
  },
  {
    id: "inv-delam",
    title: "Binder delamination at 80°C",
    status: "blocked",
    priority: "low",
    owner: "You",
    updated: "4 days ago",
    summary: "Sample A-7 delaminated at 80°C. Blocked pending a thermal cycling rig slot.",
    hypotheses: [{ id: "h1", text: "Binder glass transition too low", confidence: 0.5, status: "leading" }],
    timeline: [{ id: "t1", when: "4 days ago", kind: "observation", text: "A-7 delaminated during 80°C soak." }],
    evidence: [],
    nextSteps: ["Book thermal cycling rig.", "Request Tg spec from binder supplier."],
    entities: [{ id: "en1", kind: "sample", label: "A-7" }],
  },
];

export const APPROVALS: Approval[] = [
  {
    id: "ap1",
    title: "Draft shift handoff to night shift",
    detail: "Summarize A-7 status + the awaited DSC result and send to M. Ortiz.",
    investigation: "Uneven cathode coating — Line 3",
    requestedAt: "10 min ago",
  },
  {
    id: "ap2",
    title: "Create follow-up task: re-run DSC on a good electrode",
    detail: "Add to the team board, assigned to you, due tomorrow.",
    investigation: "Uneven cathode coating — Line 3",
    requestedAt: "12 min ago",
  },
];

export const BRIEFING: BriefingItem[] = [
  {
    id: "b1",
    kind: "result",
    title: "DSC result for A-7 arrived",
    detail: "The measurement you were waiting on is back. It may distinguish the binder vs oven hypotheses.",
    investigationId: "inv-antml",
  },
  {
    id: "b2",
    kind: "approval",
    title: "2 actions need your approval",
    detail: "A shift handoff and a follow-up task are ready to send.",
  },
  {
    id: "b3",
    kind: "procedure",
    title: "SOP-114 changed 2 days ago",
    detail: "The mixing procedure was revised — relevant to the Line 3 investigation.",
    investigationId: "inv-antml",
  },
];
