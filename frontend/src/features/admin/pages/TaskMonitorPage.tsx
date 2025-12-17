import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'

export default function TaskMonitorPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Task Monitor</h1>
          <p className="text-sm text-slate-600">Filter, inspect, and retry Celery tasks.</p>
        </div>
        <Button variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Card className="shadow-sm border-slate-200">
        <CardHeader>
          <CardTitle>Tasks</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-slate-600">
          Task filters, list, statistics, and detail panel will be implemented here.
        </CardContent>
      </Card>
    </div>
  )
}
