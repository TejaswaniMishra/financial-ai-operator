import { useState } from "react";
import { RefreshCw, Play } from "lucide-react";
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Reconciliation</h1>
          <p className="text-sm text-slate-400 mt-1">
            Match payments, settlements and bank transactions with deterministic financial rules.
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => onRunComplete()}
            disabled={isRefreshing}
            className="text-slate-300 border-slate-700 bg-slate-800/50 hover:bg-slate-800"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin text-emerald-400" : ""}`} />
            Refresh
          </Button>
          
          <Button 
            variant="default" 
            size="sm" 
            onClick={() => setDialogOpen(true)}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
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
