import { useState } from "react";
import { RefreshCw, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "../ui/button";
import { ReconciliationRunDialog } from "./reconciliation-run-dialog";

interface Props {
  onRunComplete: (result?: any) => void;
  isRefreshing: boolean;
}

export function ReconciliationHeader({ onRunComplete, isRefreshing }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-border">
        <div>
          <h1 className="text-page-title">Reconciliation</h1>
          <p className="text-secondary mt-1">
            Match payments, settlements and bank transactions with deterministic
            financial rules.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRunComplete()}
            disabled={isRefreshing}
            className="text-primary bg-primary/10 hover:bg-primary/20 border-transparent transition-colors focus-ring"
          >
            <RefreshCw
              className={cn("w-4 h-4 mr-2", isRefreshing && "animate-spin")}
            />
            Refresh
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={() => setDialogOpen(true)}
            className="shadow-sm"
          >
            <Play className="w-4 h-4 mr-2 fill-current" />
            Run Reconciliation
          </Button>
        </div>
      </div>

      <ReconciliationRunDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSuccess={(result) => {
          setDialogOpen(false);
          onRunComplete(result);
        }}
      />
    </>
  );
}
