import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

interface Props {
  onChange: (filters: {
    status?: string
    taskType?: string
    workerId?: string
    keyword?: string
  }) => void
}

const statusOptions = ['Pending', 'Running', 'Success', 'Failed', 'Retry']

export function TaskFilters({ onChange }: Props) {
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [taskType, setTaskType] = useState<string | undefined>(undefined)
  const [workerId, setWorkerId] = useState<string | undefined>(undefined)
  const [keyword, setKeyword] = useState<string | undefined>(undefined)

  const apply = () => {
    onChange({ status, taskType, workerId, keyword })
  }

  const reset = () => {
    setStatus(undefined)
    setTaskType(undefined)
    setWorkerId(undefined)
    setKeyword(undefined)
    onChange({})
  }

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-end">
      <div className="flex-1 grid grid-cols-1 md:grid-cols-4 gap-3">
        <Select value={status ?? ''} onValueChange={(v) => setStatus(v || undefined)}>
          <SelectTrigger>
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Task type (e.g. job_user_matching)"
          value={taskType ?? ''}
          onChange={(e) => setTaskType(e.target.value || undefined)}
        />
        <Input
          placeholder="Worker id"
          value={workerId ?? ''}
          onChange={(e) => setWorkerId(e.target.value || undefined)}
        />
        <Input
          placeholder="Keyword"
          value={keyword ?? ''}
          onChange={(e) => setKeyword(e.target.value || undefined)}
        />
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={reset}>
          Reset
        </Button>
        <Button onClick={apply}>Apply</Button>
      </div>
    </div>
  )
}
