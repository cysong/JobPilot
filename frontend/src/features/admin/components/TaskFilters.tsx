import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'

interface Props {
  status?: string
  taskType?: string
  workerId?: string
  keyword?: string
  taskTypesOptions: Array<{ value: string; displayName: string }>
  onChange: (filters: {
    status?: string
    taskType?: string
    workerId?: string
    keyword?: string
  }) => void
}

const statusOptions = ['Pending', 'Running', 'Success', 'Failed', 'Retry']

export function TaskFilters({
  status,
  taskType,
  workerId,
  keyword,
  taskTypesOptions,
  onChange,
}: Props) {
  const [workerInput, setWorkerInput] = useState(workerId ?? '')
  const [keywordInput, setKeywordInput] = useState(keyword ?? '')

  useEffect(() => {
    setWorkerInput(workerId ?? '')
  }, [workerId])

  useEffect(() => {
    setKeywordInput(keyword ?? '')
  }, [keyword])

  const handleSelect = (field: 'status' | 'taskType', value: string) => {
    const normalized = value === '__any__' ? undefined : value
    onChange({
      status: field === 'status' ? normalized : status,
      taskType: field === 'taskType' ? normalized : taskType,
      workerId: workerInput || undefined,
      keyword: keywordInput || undefined,
    })
  }

  const handleInput =
    (field: 'workerId' | 'keyword') =>
    (e: ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value
      if (field === 'workerId') setWorkerInput(value)
      if (field === 'keyword') setKeywordInput(value)
    }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      onChange({
        status,
        taskType,
        workerId: workerInput || undefined,
        keyword: keywordInput || undefined,
      })
    }, 300)
    return () => clearTimeout(handle)
  }, [workerInput, keywordInput])

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-end">
      <div className="flex-1 grid grid-cols-1 md:grid-cols-4 gap-3">
        <Select value={status ?? ''} onValueChange={(v) => handleSelect('status', v)}>
          <SelectTrigger>
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__any__">(Any)</SelectItem>
            {statusOptions.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={taskType ?? ''} onValueChange={(v) => handleSelect('taskType', v)}>
          <SelectTrigger>
            <SelectValue placeholder="Task type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__any__">(Any)</SelectItem>
            {taskTypesOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.displayName}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Worker id"
          value={workerInput}
          onChange={handleInput('workerId')}
        />
        <Input
          placeholder="Keyword"
          value={keywordInput}
          onChange={handleInput('keyword')}
        />
      </div>
    </div>
  )
}
