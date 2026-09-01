import { Card } from "../ui/card";
import { Info, ArrowRightLeft, Database, SearchCode } from "lucide-react";

export function ReconciliationExplanation() {
  return (
    <Card className="flex flex-col bg-slate-900/40 border-slate-800 p-5">
      <div className="flex items-center space-x-2 mb-4">
        <Info className="w-4 h-4 text-blue-400" />
        <h3 className="text-sm font-semibold text-slate-200">Reconciliation Model</h3>
      </div>
      
      <div className="space-y-4 text-xs text-slate-400">
        <p>
          The deterministic engine matches internal financial records against verified bank statements using immutable financial rules.
        </p>
        
        <ul className="space-y-3">
          <li className="flex items-start">
            <ArrowRightLeft className="w-4 h-4 text-slate-500 mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-300 font-medium">Payment → Settlement</strong><br/>
              1:1 matching or 1:N aggregations.
            </span>
          </li>
          <li className="flex items-start">
            <Database className="w-4 h-4 text-slate-500 mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-300 font-medium">Settlement → Bank Transaction</strong><br/>
              Amount, currency, and timing validation.
            </span>
          </li>
          <li className="flex items-start">
            <SearchCode className="w-4 h-4 text-slate-500 mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-slate-300 font-medium">Discrepancies</strong><br/>
              Immutable evidence preserved for investigation mapping.
            </span>
          </li>
        </ul>
      </div>
    </Card>
  );
}
