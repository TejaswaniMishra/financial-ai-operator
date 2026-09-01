"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Dialog, DialogContent } from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Search, Activity, Layers, ShieldCheck, Database, BarChart3, FileText, Settings, X } from "lucide-react";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const runCommand = (command: () => void) => {
    setOpen(false);
    command();
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm" />
      <DialogContent className="fixed left-[50%] top-[50%] z-50 w-full max-w-2xl translate-x-[-50%] translate-y-[-50%] p-0 shadow-lg border border-border rounded-xl bg-surface overflow-hidden">
        <Command className="w-full flex flex-col overflow-hidden bg-surface text-foreground h-[400px]">
          <div className="flex items-center border-b border-border px-3" cmdk-input-wrapper="">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <Command.Input 
              autoFocus
              className="flex h-12 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="Type a command or search..."
            />
            <button 
              onClick={() => setOpen(false)}
              className="p-1 rounded-sm opacity-50 hover:opacity-100 transition-opacity"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <Command.List className="max-h-[350px] overflow-y-auto overflow-x-hidden p-2">
            <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
              No results found.
            </Command.Empty>
            
            <Command.Group heading="Navigation" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Activity className="mr-2 h-4 w-4" />
                <span>Dashboard</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/reconciliation"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Layers className="mr-2 h-4 w-4" />
                <span>Reconciliation</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/discrepancies"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Search className="mr-2 h-4 w-4" />
                <span>Discrepancies</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/investigations"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <ShieldCheck className="mr-2 h-4 w-4" />
                <span>Investigations</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/transactions"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Database className="mr-2 h-4 w-4" />
                <span>Transactions</span>
              </Command.Item>
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/settings"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Settings className="mr-2 h-4 w-4" />
                <span>Settings</span>
              </Command.Item>
            </Command.Group>
            
            <Command.Separator className="my-1 h-px bg-border" />
            
            <Command.Group heading="Actions" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
              <Command.Item 
                onSelect={() => runCommand(() => router.push("/reconciliation/run"))}
                className="flex items-center px-2 py-2 text-sm rounded-md aria-selected:bg-muted aria-selected:text-foreground cursor-pointer text-foreground transition-colors"
              >
                <Layers className="mr-2 h-4 w-4 text-primary" />
                <span>Run Reconciliation Engine</span>
              </Command.Item>
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
