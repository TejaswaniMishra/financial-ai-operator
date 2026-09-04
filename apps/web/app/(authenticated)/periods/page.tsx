"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchPeriods, FinancialPeriod, PeriodListResponse } from "@/lib/api";
import { format } from "date-fns";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertCircle, Calendar, Plus } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useAuth } from "@/components/providers/auth-provider";
import { hasPermission, PERMISSIONS } from "@/lib/permissions";

function StatusBadge({ status }: { status: FinancialPeriod["status"] }) {
  switch (status) {
    case "OPEN":
      return <Badge className="bg-green-100 text-green-800 hover:bg-green-100">OPEN</Badge>;
    case "CLOSING":
      return <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">CLOSING</Badge>;
    case "CLOSED":
      return <Badge className="bg-slate-100 text-slate-800 hover:bg-slate-100">CLOSED</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function PeriodsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<PeriodListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const canCreate = hasPermission(user, PERMISSIONS.CREATE_PERIOD);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetchPeriods({ page, size: 20 });
        setData(res);
      } catch (err: any) {
        setError(err.message || "Failed to load periods");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [page]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Financial Periods</h1>
          <p className="text-muted-foreground">
            Manage period close and financial boundaries.
          </p>
        </div>
        {canCreate && (
          <Link href="/periods/new">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Open New Period
            </Button>
          </Link>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="h-24 bg-muted/50 rounded-t-lg" />
            </Card>
          ))}
        </div>
      ) : data?.items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center h-64 text-center">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No periods found</p>
            <p className="text-sm text-muted-foreground mb-4">
              There are no financial periods in the system.
            </p>
            {canCreate && (
              <Link href="/periods/new">
                <Button variant="outline">Create your first period</Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.items.map((period) => (
            <Link key={period.id} href={`/periods/${period.id}`}>
              <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-lg">{period.period_name}</CardTitle>
                    <StatusBadge status={period.status} />
                  </div>
                  <CardDescription>
                    {format(new Date(period.start_date), "MMM d, yyyy")} -{" "}
                    {format(new Date(period.end_date), "MMM d, yyyy")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground">
                    ID: <span className="font-mono">{period.id.slice(0, 8)}...</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
