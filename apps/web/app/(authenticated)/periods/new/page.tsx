"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createPeriod } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import Link from "next/link";
import { format, startOfMonth, endOfMonth, subMonths } from "date-fns";

export default function NewPeriodPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Defaults: last month
  const lastMonth = subMonths(new Date(), 1);
  const defaultStart = format(startOfMonth(lastMonth), "yyyy-MM-dd");
  const defaultEnd = format(endOfMonth(lastMonth), "yyyy-MM-dd");
  const defaultName = format(lastMonth, "MMMM yyyy");

  const [formData, setFormData] = useState({
    period_name: defaultName,
    start_date: defaultStart,
    end_date: defaultEnd,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // API expects ISO 8601 UTC strings
      const payload = {
        period_name: formData.period_name,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
      };
      const res = await createPeriod(payload);
      router.push(`/periods/${res.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create period");
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href="/periods">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Open New Period</h1>
          <p className="text-muted-foreground">
            Define a new financial period boundary for closing.
          </p>
        </div>
      </div>

      <Card>
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <CardTitle>Period Details</CardTitle>
            <CardDescription>
              A financial period represents a bounded time range for reconciliation and closing.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="period_name">Period Name</Label>
              <Input
                id="period_name"
                value={formData.period_name}
                onChange={(e) =>
                  setFormData({ ...formData, period_name: e.target.value })
                }
                placeholder="e.g. October 2023"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_date">Start Date</Label>
                <Input
                  id="start_date"
                  type="date"
                  value={formData.start_date}
                  onChange={(e) =>
                    setFormData({ ...formData, start_date: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_date">End Date (Inclusive)</Label>
                <Input
                  id="end_date"
                  type="date"
                  value={formData.end_date}
                  onChange={(e) =>
                    setFormData({ ...formData, end_date: e.target.value })
                  }
                  required
                />
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-2">
            <Link href="/periods">
              <Button variant="outline" type="button">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={loading}>
              {loading ? "Creating..." : "Open Period"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
