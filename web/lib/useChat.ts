"use client";

import { useCallback, useState } from "react";
import { sendChat, sendProjectChat } from "./api";
import type { ChatMessage } from "./types";

// Owns the conversation state and the single-turn send logic. Keeping this in a
// hook keeps the components purely presentational. When `projectId` is given, the
// turn goes to that project's scoped assistant (its own memory + integrations).
export function useChat(projectId?: number | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Bumped after each completed exchange so the sidebar knows to refresh.
  const [exchanges, setExchanges] = useState(0);

  const send = useCallback(
    async (text: string, images?: string[]) => {
      if (!text.trim() || busy) return;
      setMessages((m) => [...m, { role: "user", text, images }]);
      setBusy(true);
      try {
        const res = projectId
          ? await sendProjectChat(projectId, text, sessionId, images)
          : await sendChat(text, sessionId, images);
        setSessionId(res.session_id);
        setMessages((m) => [...m, { role: "assistant", text: res.text, sources: res.sources }]);
        setExchanges((n) => n + 1);
      } catch {
        setMessages((m) => [...m, { role: "assistant", text: "⚠️ Could not reach the assistant." }]);
      } finally {
        setBusy(false);
      }
    },
    [sessionId, busy, projectId],
  );

  const reset = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setExchanges((n) => n + 1);
  }, []);

  return { messages, busy, exchanges, send, reset };
}
