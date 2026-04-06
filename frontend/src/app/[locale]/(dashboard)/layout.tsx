"use client";

import AppShell from "@/components/layout/AppShell";
import ToastContainer from "@/components/ui/ToastContainer";
import CommandPalette from "@/components/ui/CommandPalette";
import WSEventListener from "@/components/layout/WSEventListener";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppShell>
      {children}
      <CommandPalette />
      <ToastContainer />
      <WSEventListener />
    </AppShell>
  );
}

