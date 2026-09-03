"use client"

import React, { useEffect, useState } from "react"
import { useAuth } from "@/components/providers/auth-provider"
import { fetchSecurityEvents, SecurityEvent } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

export default function SecurityEventsPage() {
  const { user } = useAuth()
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>("")

  useEffect(() => {
    if (!user || !user.permissions.includes("VIEW_AUDIT_LOGS")) {
      setError("You do not have permission to view security audit logs.")
      setLoading(false)
      return
    }

    loadEvents()
  }, [user, filterType])

  async function loadEvents() {
    try {
      setLoading(true)
      const data = await fetchSecurityEvents(filterType || undefined)
      setEvents(data)
      setError(null)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
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

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight text-slate-50">Security Audit Logs</h1>
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-slate-100">Event History</CardTitle>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-slate-800 text-sm text-slate-200 rounded border border-slate-700 p-2"
          >
            <option value="">All Events</option>
            <option value="LOGIN_SUCCESS">LOGIN_SUCCESS</option>
            <option value="LOGIN_FAILURE">LOGIN_FAILURE</option>
            <option value="LOGOUT">LOGOUT</option>
            <option value="PASSWORD_CHANGED">PASSWORD_CHANGED</option>
            <option value="ADMIN_PASSWORD_RESET">ADMIN_PASSWORD_RESET</option>
            <option value="ACCOUNT_ACTIVATED">ACCOUNT_ACTIVATED</option>
            <option value="ACCOUNT_DEACTIVATED">ACCOUNT_DEACTIVATED</option>
            <option value="ROLE_CHANGED">ROLE_CHANGED</option>
          </select>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-slate-400 py-4">Loading audit logs...</div>
          ) : (
            <div className="rounded-md border border-slate-800 overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-slate-400 bg-slate-900/50 uppercase border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Event Type</th>
                    <th className="px-4 py-3">User ID</th>
                    <th className="px-4 py-3">Actor ID</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">IP Address</th>
                  </tr>
                </thead>
                <tbody>
                  {events.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        No security events found.
                      </td>
                    </tr>
                  ) : (
                    events.map((evt) => (
                      <tr key={evt.id} className="border-b border-slate-800/50 text-slate-300">
                        <td className="px-4 py-3 whitespace-nowrap">
                          {new Date(evt.created_at + "Z").toLocaleString()}
                        </td>
                        <td className="px-4 py-3 font-medium">
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
                            <span className="text-emerald-400">Success</span>
                          ) : (
                            <span className="text-red-400">Failed</span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {evt.ip_address || "-"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
