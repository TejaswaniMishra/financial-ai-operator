import { DiscrepancyResponse } from "../../lib/api/reconciliation";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { AlertCircle, ArrowRight, FileSearch } from "lucide-react";
import Link from "next/link";

function formatCurrency(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency,
    }).format(amount);
  } catch (e) {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function SeverityBadge({ severity }: { severity: string }) {
  switch (severity.toUpperCase()) {
    case "HIGH":
      return <Badge variant="error">HIGH</Badge>;
    case "MEDIUM":
      return <Badge variant="warning">MEDIUM</Badge>;
    case "LOW":
      return <Badge variant="info">LOW</Badge>;
    default:
      return <Badge variant="outline">{severity.toUpperCase()}</Badge>;
  }
}

export function ReconciliationDiscrepancies({
  discrepancies,
}: {
  discrepancies: DiscrepancyResponse[];
}) {
  // Take only top 5 for the preview
  const previewList = discrepancies.slice(0, 5);

  return (
    <Card className="flex flex-col bg-card border-border shadow-subtle h-full overflow-hidden">
      <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between">
        <h3 className="text-card-title text-base flex items-center">
          <AlertCircle className="w-4 h-4 mr-2 text-discrepancy" />
          Reconciliation Issues
        </h3>
        {discrepancies.length > 0 && (
          <Badge
            variant="secondary"
            className="bg-destructive/10 text-destructive"
          >
            {discrepancies.length} detected
          </Badge>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {previewList.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center h-full">
            <FileSearch className="w-8 h-8 text-muted-foreground/50 mb-3" />
            <h4 className="text-sm font-medium text-foreground">
              No discrepancies
            </h4>
            <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">
              Financial records are currently fully reconciled.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {previewList.map((issue) => (
              <div
                key={issue.id}
                className="p-4 hover:bg-surface-muted/50 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <SeverityBadge severity={issue.severity} />
                    <span className="text-xs font-mono text-muted-foreground">
                      {issue.rule_code}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(issue.created_at).toLocaleDateString()}
                  </span>
                </div>

                <p className="text-sm text-foreground font-medium mb-1">
                  {issue.discrepancy_type.replace(/_/g, " ")}
                </p>

                <div className="flex items-center justify-between mt-3">
                  <div className="text-xs text-muted-foreground font-mono">
                    {issue.source_entity_type}:{" "}
                    {issue.source_entity_id.split("-")[0]}...
                  </div>

                  {issue.difference_amount !== null && issue.currency && (
                    <div className="text-sm font-semibold text-discrepancy">
                      {formatCurrency(issue.difference_amount, issue.currency)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border bg-surface mt-auto">
        <Link
          href="/discrepancies"
          className="flex items-center justify-center w-full px-3 py-2 text-xs font-medium rounded-md border border-border bg-card text-secondary hover:bg-surface-muted hover:text-foreground transition-colors"
        >
          View all discrepancies
          <ArrowRight className="w-3.5 h-3.5 ml-2" />
        </Link>
      </div>
    </Card>
  );
}
