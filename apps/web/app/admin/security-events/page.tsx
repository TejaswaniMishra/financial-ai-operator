"use client"

import React, { useEffect, useState } from "react"
import { useAuth } from "@/components/providers/auth-provider"
import { fetchSecurityEvents, SecurityEvent, SecurityEventPaginatedResponse } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

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
      <details className="text-xs text-slate-400">
        <summary className="cursor-pointer text-blue-400 hover:text-blue-300">View Metadata</summary>
        <pre className="mt-2 p-2 bg-slate-950 rounded border border-slate-800 whitespace-pre-wrap break-all">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-md">
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
        <h1 className="text-3xl font-bold tracking-tight text-slate-50">Security Audit Logs</h1>
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-slate-100">Event History</CardTitle>
          <div className="flex gap-4 items-center">
            <span className="text-sm text-slate-400">Total: {total}</span>
            <select
              value={filterType}
              onChange={(e) => {
                setFilterType(e.target.value)
                setOffset(0) // Reset pagination on filter change
              }}
              className="bg-slate-800 text-sm text-slate-200 rounded border border-slate-700 p-2"
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
            <div className="text-slate-400 py-4">Loading audit logs...</div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border border-slate-800 overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase border-b border-slate-800">
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
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                          No security events found.
                        </td>
                      </tr>
                    ) : (
                      events.map((evt) => (
                        <tr key={evt.id} className="border-b border-slate-800/50 text-slate-300 hover:bg-slate-800/30 transition-colors">
                          <td className="px-4 py-3 whitespace-nowrap text-xs">
                            {new Date(evt.created_at + "Z").toLocaleString()}
                          </td>
                          <td className="px-4 py-3 font-medium text-xs">
                            {evt.event_type}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-400">
                            {evt.user_id || "-"}
                          </td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-400">
                            {evt.actor_id || "-"}
                          </td>
                          <td className="px-4 py-3">
                            {evt.is_success ? (
                              <span className="text-emerald-400 text-xs font-semibold px-2 py-1 bg-emerald-400/10 rounded-full">Success</span>
                            ) : (
                              <span className="text-red-400 text-xs font-semibold px-2 py-1 bg-red-400/10 rounded-full">Failed</span>
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
                <button
                  disabled={!hasPrev}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-400">
                  Showing {events.length > 0 ? offset + 1 : 0} to {offset + events.length} of {total}
                </span>
                <button
                  disabled={!hasMore}
                  onClick={() => setOffset(offset + limit)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
