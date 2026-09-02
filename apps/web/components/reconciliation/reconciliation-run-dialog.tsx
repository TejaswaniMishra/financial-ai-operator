import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Play, X, Loader2, AlertCircle } from "lucide-react";
import { Button } from "../ui/button";
import {
  reconciliationApi,
  ReconciliationRunResponse,
} from "../../lib/api/reconciliation";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (result: ReconciliationRunResponse) => void;
}

export function ReconciliationRunDialog({
  open,
  onOpenChange,
  onSuccess,
}: Props) {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setError(null);

    try {
      const result = await reconciliationApi.runReconciliation();
      // On success, notify parent and close
      onSuccess(result);
      onOpenChange(false);
    } catch (err: any) {
      setError(err.message || "Failed to execute reconciliation.");
    } finally {
      setIsRunning(false);
    }
  };

  // Reset state when opened
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isRunning) {
      onOpenChange(false);
      setTimeout(() => setError(null), 200);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in" />
        <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-md translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-card p-6 shadow-lg duration-200 sm:rounded-xl">
          <div className="flex flex-col space-y-1.5 text-center sm:text-left">
            <Dialog.Title className="text-lg font-semibold leading-none tracking-tight text-foreground">
              Run Reconciliation?
            </Dialog.Title>
            <Dialog.Description className="text-sm text-muted-foreground mt-2">
              This will run the deterministic reconciliation engine against the
              current financial records.
            </Dialog.Description>
          </div>

          {error && (
            <div className="p-3 mt-2 bg-destructive/10 border border-destructive/20 rounded-md flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-destructive mt-0.5 shrink-0" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {isRunning && (
            <div className="p-3 mt-2 bg-surface-muted rounded-md border border-border flex flex-col space-y-1">
              <span className="text-sm font-medium text-foreground flex items-center">
                <Loader2 className="w-3.5 h-3.5 mr-2 animate-spin text-primary" />
                Running reconciliation...
              </span>
              <span className="text-xs text-muted-foreground ml-5 pl-0.5">
                Matching payments, settlements and bank transactions.
              </span>
            </div>
          )}

          <div className="flex justify-end space-x-3 mt-4">
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isRunning}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRun}
              disabled={isRunning}
              className="min-w-[140px] shadow-sm"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2 fill-current" />
                  Run Reconciliation
                </>
              )}
            </Button>
          </div>

          <Dialog.Close
            disabled={isRunning}
            className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring disabled:pointer-events-none data-[state=open]:bg-surface-muted data-[state=open]:text-muted-foreground"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
