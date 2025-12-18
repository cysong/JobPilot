import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { useDashboardStats } from '../hooks/useDashboardStats'
import { useWorkerStatus } from '../hooks/useWorkerStatus'
import { DashboardStats } from '../components/DashboardStats'
import { WorkerMonitor } from '../components/WorkerMonitor'

export default function AdminDashboardPage() {
  const statsQuery = useDashboardStats()
  const workerQuery = useWorkerStatus()

  const refresh = () => {
    statsQuery.refetch()
    workerQuery.refetch()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
          <p className="text-sm text-slate-600">Monitor system health and worker status.</p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw
            className={`h-4 w-4 mr-2 ${statsQuery.isFetching || workerQuery.isFetching ? 'animate-spin' : ''}`}
          />
          Refresh
        </Button>
      </div>

      <DashboardStats data={statsQuery.data} isLoading={statsQuery.isLoading} />
      <WorkerMonitor data={workerQuery.data} isLoading={workerQuery.isLoading} />
    </div>
  )
}
