"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { TopNav } from "@/components/layout/top-nav";
import { CommandPalette } from "@/components/global/command-palette";

const AUTH_PATHS = new Set(["/login", "/signup"]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = AUTH_PATHS.has(pathname);

  if (isAuthPage) {
    return <main className="min-h-screen w-full">{children}</main>;
  }

  return (
    <>
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 h-screen overflow-hidden bg-background">
        <TopNav />
        <main className="flex-1 overflow-y-auto focus:outline-none">
          <div className="mx-auto w-full max-w-[1600px] p-4 sm:p-6 lg:p-8 lg:py-10">
            {children}
          </div>
        </main>
      </div>
      <CommandPalette />
    </>
  );
}