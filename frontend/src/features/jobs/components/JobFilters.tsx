import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { useJobFilterOptions } from '@/features/jobs/hooks/useJobs'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from '@/components/ui/accordion'

export function JobFilters() {
    const [searchParams, setSearchParams] = useSearchParams()
    const { data: options, isLoading } = useJobFilterOptions()

    // Local state for filters to avoid excessive URL updates
    const [selectedCities, setSelectedCities] = useState<string[]>([])
    const [selectedWorkTypes, setSelectedWorkTypes] = useState<string[]>([])
    const [selectedCompanies, setSelectedCompanies] = useState<string[]>([])

    // Sync from URL to local state on mount/update
    useEffect(() => {
        setSelectedCities(searchParams.getAll('location_cities'))
        setSelectedWorkTypes(searchParams.getAll('work_types'))
        setSelectedCompanies(searchParams.getAll('companies'))
    }, [searchParams])

    const updateFilters = (
        key: string,
        values: string[]
    ) => {
        const newParams = new URLSearchParams(searchParams)
        newParams.delete(key)
        values.forEach((v) => newParams.append(key, v))
        newParams.set('page', '1') // Reset pagination
        setSearchParams(newParams)
    }

    const handleCheckboxChange = (
        key: string,
        value: string,
        currentValues: string[],
        setValues: (v: string[]) => void
    ) => {
        const newValues = currentValues.includes(value)
            ? currentValues.filter((v) => v !== value)
            : [...currentValues, value]

        setValues(newValues)
        updateFilters(key, newValues)
    }

    const clearFilters = () => {
        const newParams = new URLSearchParams(searchParams)
        newParams.delete('location_cities')
        newParams.delete('work_types')
        newParams.delete('companies')
        newParams.set('page', '1')
        setSearchParams(newParams)
    }

    if (isLoading) {
        return (
            <div className="flex justify-center p-4">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
        )
    }

    if (!options) return null

    const hasActiveFilters =
        selectedCities.length > 0 ||
        selectedWorkTypes.length > 0 ||
        selectedCompanies.length > 0

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h3 className="font-semibold text-lg text-slate-900">Filters</h3>
                {hasActiveFilters && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearFilters}
                        className="text-indigo-600 hover:text-indigo-700 h-auto p-0 hover:bg-transparent font-medium"
                    >
                        Clear all
                    </Button>
                )}
            </div>

            <Accordion type="multiple" defaultValue={['locations', 'workTypes']} className="w-full">
                {/* Locations */}
                <AccordionItem value="locations" className="border-none">
                    <AccordionTrigger className="py-2 hover:no-underline text-sm font-semibold">
                        Locations
                    </AccordionTrigger>
                    <AccordionContent>
                        <div className="space-y-2 pt-1">
                            {options.location_cities.map((city) => (
                                <div key={city} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={`city-${city}`}
                                        checked={selectedCities.includes(city)}
                                        onCheckedChange={() =>
                                            handleCheckboxChange('location_cities', city, selectedCities, setSelectedCities)
                                        }
                                    />
                                    <Label
                                        htmlFor={`city-${city}`}
                                        className="text-sm font-normal text-slate-600 cursor-pointer"
                                    >
                                        {city}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    </AccordionContent>
                </AccordionItem>

                <Separator className="my-4" />

                {/* Work Types */}
                <AccordionItem value="workTypes" className="border-none">
                    <AccordionTrigger className="py-2 hover:no-underline text-sm font-semibold">
                        Work Type
                    </AccordionTrigger>
                    <AccordionContent>
                        <div className="space-y-2 pt-1">
                            {options.work_types.map((type) => (
                                <div key={type} className="flex items-center space-x-2">
                                    <Checkbox
                                        id={`type-${type}`}
                                        checked={selectedWorkTypes.includes(type)}
                                        onCheckedChange={() =>
                                            handleCheckboxChange('work_types', type, selectedWorkTypes, setSelectedWorkTypes)
                                        }
                                    />
                                    <Label
                                        htmlFor={`type-${type}`}
                                        className="text-sm font-normal text-slate-600 cursor-pointer"
                                    >
                                        {type}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    </AccordionContent>
                </AccordionItem>

                <Separator className="my-4" />

                {/* Companies */}
                <AccordionItem value="companies" className="border-none">
                    <AccordionTrigger className="py-2 hover:no-underline text-sm font-semibold">
                        Company
                    </AccordionTrigger>
                    <AccordionContent>
                        <ScrollArea className="h-60 pr-4">
                            <div className="space-y-2 pt-1">
                                {options.companies.map((company) => (
                                    <div key={company} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`company-${company}`}
                                            checked={selectedCompanies.includes(company)}
                                            onCheckedChange={() =>
                                                handleCheckboxChange('companies', company, selectedCompanies, setSelectedCompanies)
                                            }
                                        />
                                        <Label
                                            htmlFor={`company-${company}`}
                                            className="text-sm font-normal text-slate-600 cursor-pointer"
                                        >
                                            {company}
                                        </Label>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </AccordionContent>
                </AccordionItem>
            </Accordion>
        </div>
    )
}
