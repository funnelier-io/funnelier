"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import Sidebar from "./Sidebar";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const { checkAuth, isLoading, isAuthenticated } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-4xl mb-4">🎯</div>
          <div className="text-gray-400 text-sm">در حال بارگذاری...</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <>
      <Sidebar />
      <main className="mr-60 p-6 min-h-screen">{children}</main>
    </>
  );
}

