import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertCircle, Play, X } from "lucide-react";
import { Button } from "../ui/button";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function ReconciliationRunDialog({ open, onOpenChange, onSuccess }: Props) {
  // Logic to be implemented in Execution Flow commit
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-md translate-x-[-50%] translate-y-[-50%] gap-4 border border-slate-800 bg-slate-950 p-6 shadow-lg duration-200 sm:rounded-xl">
          <div className="flex flex-col space-y-1.5 text-center sm:text-left">
            <Dialog.Title className="text-lg font-semibold leading-none tracking-tight text-slate-100">
              Run Reconciliation?
            </Dialog.Title>
            <Dialog.Description className="text-sm text-slate-400 mt-2">
              This will process the current financial records using the deterministic reconciliation engine.
            </Dialog.Description>
          </div>
          
          <div className="flex justify-end space-x-2 mt-4">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={() => onSuccess()} className="bg-emerald-600 hover:bg-emerald-500 text-white">
              <Play className="w-4 h-4 mr-2" />
              Run
            </Button>
          </div>
          
          <Dialog.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-slate-950 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-slate-300 focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-slate-800 data-[state=open]:text-slate-400">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
