"use client";

import type { Investigation } from "@/lib/types";
import { Icon, KIND_ICON } from "@/components/Icon";
import { Confidence, EntityChip } from "@/components/ui";

export function StatePanel({ investigation }: { investigation: Investigation }) {
  return (
    <>
      <p className="lead-summary">{investigation.summary}</p>

      <div className="block">
        <div className="block-h"><Icon name="sparkle" size={13} /> Current understanding</div>
        <div className="hyps">
          {investigation.hypotheses.map((h) => (
            <div
              key={h.id}
              className={`hyp ${h.status === "leading" ? "leading" : ""} ${h.status === "ruled-out" ? "ruled-out" : ""}`}
            >
              <div className="hyp-left">
                <span>{h.text}</span>
                <span className="hyp-status">{h.status.replace("-", " ")}</span>
              </div>
              <Confidence value={h.confidence} />
            </div>
          ))}
        </div>
      </div>

      <div className="block">
        <div className="block-h"><Icon name="clock" size={13} /> Timeline</div>
        <div className="tl">
          {investigation.timeline.map((e) => (
            <div key={e.id} className="tl-item">
              <span className="tl-ic"><Icon name={KIND_ICON[e.kind] ?? "edit"} size={13} /></span>
              <div className="tl-body">
                <div>{e.text}</div>
                <div className="tl-when">{e.when}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="block">
        <div className="block-h"><Icon name="file" size={13} /> Evidence</div>
        {investigation.evidence.length === 0 ? (
          <div className="dim">No linked evidence yet.</div>
        ) : (
          <div className="ev-list">
            {investigation.evidence.map((ev) => (
              <div key={ev.id} className="ev">
                <Icon name="link" size={14} />
                <a href={ev.url}>{ev.title}</a>
                <span className="dim">· {ev.source}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="block">
        <div className="block-h"><Icon name="arrowRight" size={13} /> Suggested next steps</div>
        <div className="steps">
          {investigation.nextSteps.map((s, i) => (
            <div key={i} className="step">
              <span className="step-check" />
              <span>{s}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="block">
        <div className="block-h"><Icon name="layers" size={13} /> Related</div>
        <div className="chips">
          {investigation.entities.map((e) => (
            <EntityChip key={e.id} kind={e.kind} label={e.label} />
          ))}
        </div>
      </div>
    </>
  );
}
