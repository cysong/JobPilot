import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
          <p className="text-sm text-slate-600">Monitor system health and worker status.</p>
        </div>
        <Button variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle>Dashboard Stats</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            Stats cards coming soon (users, jobs, matches, applications, tasks).
          </CardContent>
        </Card>

        <Card className="shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle>Workers</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            Worker monitor (active/queued/running, worker list) will appear here.
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
