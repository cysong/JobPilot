import { useState } from 'react'
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

interface FilterDropdownProps {
  label: string
  options: string[]
  selectedValues: string[]
  onSelectionChange: (values: string[]) => void
  searchPlaceholder?: string
  emptyText?: string
  className?: string
}

/**
 * Reusable multi-select filter dropdown component using Command UI
 * Allows searching and selecting multiple options with checkmarks
 */
export function FilterDropdown({
  label,
  options,
  selectedValues,
  onSelectionChange,
  searchPlaceholder = 'Search...',
  emptyText = 'No options found.',
  className,
}: FilterDropdownProps) {
  const [open, setOpen] = useState(false)

  const handleSelect = (value: string) => {
    const newValues = selectedValues.includes(value)
      ? selectedValues.filter((v) => v !== value)
      : [...selectedValues, value]

    onSelectionChange(newValues)
  }

  const displayText = selectedValues.length > 0
    ? `${label} (${selectedValues.length})`
    : label

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
            className
          )}
        >
          <span className="truncate">{displayText}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="start">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
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
                          : 'opacity-50'
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
