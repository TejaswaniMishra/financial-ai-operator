"use client"

import React, { useEffect, useState } from "react"
import { useAuth } from "@/components/providers/auth-provider"
import { fetchSecurityEvents, SecurityEvent, SecurityEventPaginatedResponse } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

export default function SecurityEventsPage() {
  const { user } = useAuth()
  const [eventsData, setEventsData] = useState<SecurityEventPaginatedResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>("")
  const [offset, setOffset] = useState<number>(0)
  const limit = 50

  useEffect(() => {
    if (!user || !user.permissions.includes("VIEW_AUDIT_LOGS")) {
      setError("You do not have permission to view security audit logs.")
      setLoading(false)
      return
    }

    loadEvents()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, filterType, offset])

  async function loadEvents() {
    try {
      setLoading(true)
      const data = await fetchSecurityEvents(filterType || undefined, limit, offset)
      setEventsData(data)
      setError(null)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const renderMetadata = (payload: any) => {
    if (!payload || Object.keys(payload).length === 0) return "-"
    return (
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer text-primary hover:text-primary/80">View Metadata</summary>
        <pre className="mt-2 p-2 bg-surface-muted rounded border border-border whitespace-pre-wrap break-all text-foreground">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-error/10 border border-error/20 text-error p-4 rounded-md">
          {error}
        </div>
      </div>
    )
  }

  const events = eventsData?.items || []
  const total = eventsData?.total || 0
  const hasMore = offset + limit < total
  const hasPrev = offset > 0

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-page-title">Security Audit Logs</h1>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Event History</CardTitle>
          <div className="flex gap-4 items-center">
            <span className="text-sm text-muted-foreground">Total: {total}</span>
            <select
              value={filterType}
              onChange={(e) => {
                setFilterType(e.target.value)
                setOffset(0) // Reset pagination on filter change
              }}
              className="h-10 bg-background text-sm text-foreground rounded-md border border-input px-3 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
            >
              <option value="">All Events</option>
              <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
              <option value="LOGIN_FAILURE">LOGIN_FAILURE</option>
              <option value="LOGOUT">LOGOUT</option>
              <option value="SESSION_REJECTED">SESSION_REJECTED</option>
              <option value="TOKEN_REVOKED">TOKEN_REVOKED</option>
              <option value="PASSWORD_CHANGED">PASSWORD_CHANGED</option>
              <option value="ADMIN_PASSWORD_RESET">ADMIN_PASSWORD_RESET</option>
              <option value="ACCOUNT_ACTIVATED">ACCOUNT_ACTIVATED</option>
              <option value="ACCOUNT_DEACTIVATED">ACCOUNT_DEACTIVATED</option>
              <option value="ROLE_CHANGED">ROLE_CHANGED</option>
              <option value="AUTHORIZATION_DENIED">AUTHORIZATION_DENIED</option>
              <option value="ACTION_REQUEST_CREATED">ACTION_REQUEST_CREATED</option>
              <option value="ACTION_REQUEST_APPROVED">ACTION_REQUEST_APPROVED</option>
              <option value="ACTION_REQUEST_REJECTED">ACTION_REQUEST_REJECTED</option>
              <option value="ACTION_REQUEST_CANCELLED">ACTION_REQUEST_CANCELLED</option>
              <option value="ACTION_EXECUTION_STARTED">ACTION_EXECUTION_STARTED</option>
              <option value="ACTION_EXECUTION_SUCCEEDED">ACTION_EXECUTION_SUCCEEDED</option>
              <option value="ACTION_EXECUTION_FAILED">ACTION_EXECUTION_FAILED</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-muted-foreground py-4">Loading audit logs...</div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border border-border overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-muted-foreground bg-surface-muted uppercase border-b border-border">
                    <tr>
                      <th className="px-4 py-3">Timestamp</th>
                      <th className="px-4 py-3">Event Type</th>
                      <th className="px-4 py-3">User/Target ID</th>
                      <th className="px-4 py-3">Actor ID</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">IP Address</th>
                      <th className="px-4 py-3">Metadata</th>
                    </tr>
                  </thead>
                  <tbody>
                    {events.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                          No security events found.
                        </td>
                      </tr>
                    ) : (
                      events.map((evt) => (
                        <tr key={evt.id} className="border-b border-border text-foreground hover:bg-surface-muted/50 transition-colors">
                          <td className="px-4 py-3 whitespace-nowrap text-xs">
                            {new Date(evt.created_at + "Z").toLocaleString()}
                          </td>
                          <td className="px-4 py-3 font-medium text-xs">
                            {evt.event_type}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                            {evt.user_id || "-"}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                            {evt.actor_id || "-"}
                          </td>
                          <td className="px-4 py-3">
                            {evt.is_success ? (
                              <Badge tone="emerald">Success</Badge>
                            ) : (
                              <Badge tone="red">Failed</Badge>
                            )}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs">
                            {evt.ip_address || "-"}
                          </td>
                          <td className="px-4 py-3">
                            {renderMetadata(evt.metadata_payload)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div className="flex justify-between items-center">
                <Button
                  disabled={!hasPrev}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  variant="outline"
                  size="sm"
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Showing {events.length > 0 ? offset + 1 : 0} to {offset + events.length} of {total}
                </span>
                <Button
                  disabled={!hasMore}
                  onClick={() => setOffset(offset + limit)}
                  variant="outline"
                  size="sm"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}