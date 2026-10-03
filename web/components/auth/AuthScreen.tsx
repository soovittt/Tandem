"use client";

import { useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { useAuth } from "@/lib/auth";

const FEATURES = [
  { icon: "sparkle", title: "Remembers your work", text: "Persistent memory across sessions, scoped to each project." },
  { icon: "book", title: "Connects your systems", text: "Notebooks, tickets, drives — with source-linked answers." },
  { icon: "alert", title: "Your data, your control", text: "Runs on your private inference endpoint, fully audit-logged." },
];

export function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, name, password, org);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const isLogin = mode === "login";

  return (
    <div className="auth">
      <aside className="auth-hero">
        <div className="auth-logo">
          <span className="nav-ws-badge">T</span> Tandem
        </div>
        <h1 className="auth-hero-title">
          Your private AI<br />work partner.
        </h1>
        <p className="auth-hero-sub">
          An always-on assistant for technical teams — it remembers, connects your tools,
          and advances the work. Not a chatbot. A partner.
        </p>
        <ul className="auth-features">
          {FEATURES.map((f) => (
            <li key={f.title}>
              <span className="auth-feat-ic"><Icon name={f.icon} size={16} /></span>
              <div>
                <div className="auth-feat-title">{f.title}</div>
                <div className="auth-feat-text">{f.text}</div>
              </div>
            </li>
          ))}
        </ul>
      </aside>

      <main className="auth-panel">
        <div className="auth-card">
          <div className="auth-card-logo">
            <span className="nav-ws-badge">T</span> Tandem
          </div>
          <h2 className="auth-title">{isLogin ? "Welcome back" : "Create your account"}</h2>
          <p className="auth-sub">
            {isLogin ? "Sign in to your workspace." : "Spin up your private workspace in seconds."}
          </p>

          <form onSubmit={submit} className="auth-form">
            {!isLogin && (
              <>
                <label>
                  Your name
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Chen" required />
                </label>
                <label>
                  Workspace name
                  <input value={org} onChange={(e) => setOrg(e.target.value)} placeholder="Aurora Materials" required />
                </label>
              </>
            )}
            <label>
              Work email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" required />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required minLength={8} />
            </label>

            {error && <div className="auth-error">{error}</div>}

            <button className="btn btn-primary auth-submit" disabled={busy}>
              {busy ? "…" : isLogin ? "Sign in" : "Sign up"}
            </button>
          </form>

          <div className="auth-switch">
            {isLogin ? (
              <>New to Tandem? <button onClick={() => setMode("signup")}>Sign up</button></>
            ) : (
              <>Already have an account? <button onClick={() => setMode("login")}>Sign in</button></>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
