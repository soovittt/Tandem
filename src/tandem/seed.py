"""
Seed a new organization with a demo project + investigations, so a fresh signup
lands in a live workspace instead of an empty one. (Real accounts would import
their own data via integrations.)
"""

from __future__ import annotations

import json

from sqlmodel import Session

from tandem.models import Integration, Investigation, Project

_INVESTIGATIONS = [
    {
        "title": "Uneven cathode coating — Line 3",
        "status": "awaiting",
        "priority": "high",
        "owner": "You",
        "updated": "20 min ago",
        "summary": "Battery electrodes from Line 3 show uneven coating thickness. Two candidate causes; awaiting a DSC result to distinguish them.",
        "hypotheses": [
            {"id": "h1", "text": "Slurry viscosity drift (binder lot change)", "confidence": 0.55, "status": "leading"},
            {"id": "h2", "text": "Coating oven running ~10°C hot", "confidence": 0.3, "status": "considered"},
            {"id": "h3", "text": "Comma-bar gap misaligned", "confidence": 0.15, "status": "ruled-out"},
        ],
        "timeline": [
            {"id": "t1", "when": "3 days ago", "kind": "observation", "text": "Photo of uneven coating on sample A-7 uploaded."},
            {"id": "t2", "when": "3 days ago", "kind": "note", "text": "Similar appearance last month had two different root causes."},
            {"id": "t3", "when": "2 days ago", "kind": "procedure", "text": "SOP-114 (mixing) was revised — new rest time."},
            {"id": "t4", "when": "20 min ago", "kind": "result", "text": "DSC result for A-7 arrived — under review."},
        ],
        "evidence": [
            {"id": "e1", "title": "Sample A-7 coating photo", "source": "Mobile capture", "url": "#"},
            {"id": "e2", "title": "XRD export — batch 0912", "source": "Instrument export", "url": "#"},
            {"id": "e3", "title": "SOP-114 rev C", "source": "Benchling", "url": "#"},
        ],
        "entities": [
            {"id": "en1", "kind": "sample", "label": "A-7"},
            {"id": "en2", "kind": "equipment", "label": "Coating line 3"},
            {"id": "en3", "kind": "procedure", "label": "SOP-114"},
            {"id": "en4", "kind": "person", "label": "M. Ortiz (night shift)"},
        ],
        "nextSteps": [
            "Compare DSC of A-7 vs a good electrode to confirm binder hypothesis.",
            "Pull last 5 viscosity readings for the new binder lot.",
        ],
    },
    {
        "title": "Capacity fade after 200 cycles",
        "status": "active",
        "priority": "medium",
        "owner": "R. Chen",
        "updated": "yesterday",
        "summary": "Cells lose ~8% capacity by cycle 200 vs the 3% target. Investigating electrolyte formulation.",
        "hypotheses": [
            {"id": "h1", "text": "SEI growth from additive shortfall", "confidence": 0.6, "status": "leading"},
            {"id": "h2", "text": "Cathode cracking at high C-rate", "confidence": 0.35, "status": "considered"},
        ],
        "timeline": [
            {"id": "t1", "when": "1 week ago", "kind": "observation", "text": "Cycle-life test flagged fade at cycle 180."},
            {"id": "t2", "when": "3 days ago", "kind": "decision", "text": "Decided to pull cells for post-mortem EIS."},
        ],
        "evidence": [{"id": "e1", "title": "Cycler log — cell group C", "source": "Instrument export", "url": "#"}],
        "entities": [
            {"id": "en1", "kind": "equipment", "label": "Cycler bay 2"},
            {"id": "en2", "kind": "person", "label": "R. Chen"},
        ],
        "nextSteps": ["Run EIS on 3 aged cells.", "Check additive lot certificate."],
    },
    {
        "title": "Binder delamination at 80°C",
        "status": "blocked",
        "priority": "low",
        "owner": "You",
        "updated": "4 days ago",
        "summary": "Sample A-7 delaminated at 80°C. Blocked pending a thermal cycling rig slot.",
        "hypotheses": [{"id": "h1", "text": "Binder glass transition too low", "confidence": 0.5, "status": "leading"}],
        "timeline": [{"id": "t1", "when": "4 days ago", "kind": "observation", "text": "A-7 delaminated during 80°C soak."}],
        "evidence": [],
        "entities": [{"id": "en1", "kind": "sample", "label": "A-7"}],
        "nextSteps": ["Book thermal cycling rig.", "Request Tg spec from binder supplier."],
    },
]

_INTEGRATIONS = [
    {"kind": "benchling", "name": "Benchling (ELN)", "status": "connected"},
    {"kind": "instruments", "name": "Instrument exports", "status": "connected"},
    {"kind": "jira", "name": "Jira", "status": "connected"},
    {"kind": "sharepoint", "name": "SharePoint", "status": "available"},
    {"kind": "slack", "name": "Slack", "status": "available"},
]


def seed_demo(session: Session, org_id: int) -> None:
    """Create a demo project with investigations + integrations for a new org."""
    project = Project(org_id=org_id, name="Battery R&D", key="BAT", description="Cathode & electrolyte investigations")
    session.add(project)
    session.commit()
    session.refresh(project)

    for item in _INVESTIGATIONS:
        session.add(
            Investigation(
                project_id=project.id,
                title=item["title"],
                status=item["status"],
                priority=item["priority"],
                owner=item["owner"],
                summary=item["summary"],
                updated=item["updated"],
                hypotheses_json=json.dumps(item["hypotheses"]),
                timeline_json=json.dumps(item["timeline"]),
                evidence_json=json.dumps(item["evidence"]),
                entities_json=json.dumps(item["entities"]),
                next_steps_json=json.dumps(item["nextSteps"]),
            )
        )
    for integ in _INTEGRATIONS:
        session.add(Integration(project_id=project.id, kind=integ["kind"], name=integ["name"], status=integ["status"]))
    session.commit()
