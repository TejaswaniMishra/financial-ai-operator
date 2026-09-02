import { Card } from "../ui/card";
import { Info, ArrowRightLeft, Database, SearchCode } from "lucide-react";

export function ReconciliationExplanation() {
  return (
    <Card className="flex flex-col bg-card border-border shadow-subtle p-5">
      <div className="flex items-center space-x-2 mb-4">
        <Info className="w-4 h-4 text-primary" />
        <h3 className="text-card-title text-base">Reconciliation Model</h3>
      </div>

      <div className="space-y-4 text-xs text-secondary">
        <p>
          The deterministic engine matches internal financial records against
          verified bank statements using immutable financial rules.
        </p>

        <ul className="space-y-3">
          <li className="flex items-start">
            <ArrowRightLeft className="w-4 h-4 text-muted-foreground mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-foreground font-medium">
                Payment → Settlement
              </strong>
              <br />
              1:1 matching or 1:N aggregations.
            </span>
          </li>
          <li className="flex items-start">
            <Database className="w-4 h-4 text-muted-foreground mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-foreground font-medium">
                Settlement → Bank Transaction
              </strong>
              <br />
              Amount, currency, and timing validation.
            </span>
          </li>
          <li className="flex items-start">
            <SearchCode className="w-4 h-4 text-muted-foreground mr-2 mt-0.5 shrink-0" />
            <span>
              <strong className="text-foreground font-medium">
                Discrepancies
              </strong>
              <br />
              Immutable evidence preserved for investigation mapping.
            </span>
          </li>
        </ul>
      </div>
    </Card>
  );
}
