"use client";

import { AppShell } from "@/components/app/AppShell";
import { AuthScreen } from "@/components/auth/AuthScreen";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { ready, user } = useAuth();
  if (!ready) return <div className="boot">Loading…</div>;
  return user ? <AppShell /> : <AuthScreen />;
}
