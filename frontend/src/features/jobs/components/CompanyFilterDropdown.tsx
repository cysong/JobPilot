import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/utils/cn'
import { useCompanyFilterOptions } from '@/features/jobs/hooks/useJobs'

interface CompanyFilterDropdownProps {
  selectedValues: string[]
  onSelectionChange: (values: string[]) => void
  className?: string
}

/**
 * Company filter dropdown with debounced remote search.
 */
export function CompanyFilterDropdown({
  selectedValues,
  onSelectionChange,
  className,
}: CompanyFilterDropdownProps) {
  const [open, setOpen] = useState(false)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [debouncedKeyword, setDebouncedKeyword] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(searchKeyword.trim())
    }, 300)

    return () => window.clearTimeout(timer)
  }, [searchKeyword])

  const { data: remoteOptions, isFetching } = useCompanyFilterOptions(
    debouncedKeyword,
    20,
    open,
  )

  const options = useMemo(() => {
    const merged: string[] = []
    const seen = new Set<string>()

    const pushUnique = (value: string) => {
      const key = value.trim().toLowerCase()
      if (!key || seen.has(key)) return
      seen.add(key)
      merged.push(value)
    }

    selectedValues.forEach(pushUnique)
    ;(remoteOptions ?? []).forEach(pushUnique)

    return merged
  }, [remoteOptions, selectedValues])

  const handleSelect = (value: string) => {
    const newValues = selectedValues.includes(value)
      ? selectedValues.filter((v) => v !== value)
      : [...selectedValues, value]

    onSelectionChange(newValues)
  }

  const displayText = selectedValues.length > 0
    ? `Company (${selectedValues.length})`
    : 'Company'

  const emptyText = debouncedKeyword.length > 0
    ? 'No companies found'
    : 'Type to search companies...'

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'justify-between min-w-[180px]',
            selectedValues.length > 0 && 'border-indigo-500 bg-indigo-50',
            className,
          )}
        >
          <span className="truncate">{displayText}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            value={searchKeyword}
            onValueChange={setSearchKeyword}
            placeholder="Search companies..."
          />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            {isFetching && (
              <div className="px-3 py-2 text-xs text-slate-500">Searching...</div>
            )}
            <CommandGroup>
              {options.map((option) => {
                const isSelected = selectedValues.includes(option)
                return (
                  <CommandItem
                    key={option}
                    value={option}
                    onSelect={() => handleSelect(option)}
                    className="cursor-pointer"
                  >
                    <div
                      className={cn(
                        'mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-slate-300',
                        isSelected
                          ? 'bg-indigo-600 border-indigo-600 text-white'
                          : 'opacity-50',
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <span className="flex-1">{option}</span>
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
