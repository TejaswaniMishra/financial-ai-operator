export function ReconciliationSkeleton() {
  return (
    <div className="space-y-8 pb-12 animate-pulse">
      <div className="flex justify-between items-center h-16 border-b border-border mb-8">
        <div className="space-y-2">
          <div className="h-6 w-48 bg-surface-muted rounded"></div>
          <div className="h-4 w-72 bg-surface-muted/50 rounded"></div>
        </div>
        <div className="h-10 w-32 bg-surface-muted rounded-md"></div>
      </div>

      <div className="h-24 w-full bg-surface-muted/40 rounded-xl"></div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-surface-muted/30 rounded-xl"></div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-96 bg-surface-muted/20 rounded-xl"></div>
        <div className="h-96 bg-surface-muted/20 rounded-xl"></div>
      </div>
    </div>
  );
}
