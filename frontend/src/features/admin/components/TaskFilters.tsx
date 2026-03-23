import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'

interface Props {
  status?: string
  taskType?: string
  workerId?: string
  keyword?: string
  taskTypesOptions: Array<{ value: string; displayName: string }>
  workerOptions: string[]
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
  workerOptions,
  onChange,
}: Props) {
  const [keywordInput, setKeywordInput] = useState(keyword ?? '')

  useEffect(() => {
    setKeywordInput(keyword ?? '')
  }, [keyword])

  const handleSelect = (field: 'status' | 'taskType', value: string) => {
    const normalized = value === '__any__' ? undefined : value
    onChange({
      status: field === 'status' ? normalized : status,
      taskType: field === 'taskType' ? normalized : taskType,
      workerId,
      keyword: keywordInput || undefined,
    })
  }

  const handleInput = (e: ChangeEvent<HTMLInputElement>) => {
    setKeywordInput(e.target.value)
  }

  const handleWorkerSelect = (value: string) => {
    onChange({
      status,
      taskType,
      workerId: value === '__any__' ? undefined : value,
      keyword: keywordInput || undefined,
    })
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      onChange({
        status,
        taskType,
        workerId,
        keyword: keywordInput || undefined,
      })
    }, 300)
    return () => clearTimeout(handle)
  }, [keywordInput])

  const handleClearKeyword = () => {
    setKeywordInput('')
    onChange({
      status,
      taskType,
      workerId,
      keyword: undefined,
    })
  }

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
        <Select value={workerId ?? ''} onValueChange={handleWorkerSelect}>
          <SelectTrigger>
            <SelectValue placeholder="Worker" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__any__">(Any)</SelectItem>
            {workerOptions.map((id) => (
              <SelectItem key={id} value={id}>
                {id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative">
          <Input
            placeholder="Keyword"
            className="pr-10"
            value={keywordInput}
            onChange={handleInput}
          />
          {keywordInput && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0 hover:bg-transparent"
              onClick={handleClearKeyword}
            >
              <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
