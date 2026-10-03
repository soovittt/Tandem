"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useChat } from "@/lib/useChat";
import { Icon } from "@/components/Icon";

export function AssistantPanel({
  investigationTitle,
  projectId,
}: {
  investigationTitle: string;
  projectId: number | null;
}) {
  const { messages, busy, send } = useChat(projectId);
  const [text, setText] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  function submit() {
    if (!text.trim() || busy) return;
    send(text, images);
    setText("");
    setImages([]);
  }

  function onFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    for (const file of files) {
      const reader = new FileReader();
      reader.onload = () => setImages((imgs) => [...imgs, reader.result as string]);
      reader.readAsDataURL(file);
    }
    e.target.value = "";
  }

  return (
    <div className="asst">
      <div className="asst-h">
        <Icon name="sparkle" size={16} /> Assistant
      </div>

      <div className="asst-body">
        {messages.length === 0 && (
          <div className="dim" style={{ fontSize: 12.5 }}>
            Ask about “{investigationTitle}”. I have its context, evidence, and history — I can
            compare runs, weigh hypotheses, and draft the next step for your approval.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "user" : "asst"}`}>
            {m.images?.map((src, j) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={j} className="msg-thumb" src={src} alt="attachment" />
            ))}
            {m.text}
            {m.sources && m.sources.length > 0 && (
              <ul className="msg-sources">
                {m.sources.map((s, j) => (
                  <li key={j}>
                    <a href={s.url} target="_blank" rel="noreferrer">{s.title || s.url}</a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {busy && <div className="msg asst"><em>thinking…</em></div>}
        <div ref={endRef} />
      </div>

      <div className="asst-composer">
        {images.length > 0 && (
          <div className="asst-attach">
            {images.map((src, i) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={i} src={src} alt="attachment" />
            ))}
          </div>
        )}
        <div className="asst-input">
          <button className="btn-icon" onClick={() => fileRef.current?.click()} title="Attach image">
            <Icon name="paperclip" size={16} />
          </button>
          <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={onFiles} />
          <textarea
            value={text}
            placeholder="Message the assistant…"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button className="btn-icon" onClick={submit} disabled={busy} title="Send">
            <Icon name="send" size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
