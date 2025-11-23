import { useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export function JobSearch() {
    const [searchParams, setSearchParams] = useSearchParams()
    const initialKeyword = searchParams.get('keyword') || ''
    const [keyword, setKeyword] = useState(initialKeyword)

    // Sync local state with URL params
    useEffect(() => {
        setKeyword(searchParams.get('keyword') || '')
    }, [searchParams])

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault()
        updateSearchParams(keyword)
    }

    const handleClear = () => {
        setKeyword('')
        updateSearchParams('')
    }

    const updateSearchParams = (value: string) => {
        const newParams = new URLSearchParams(searchParams)
        if (value) {
            newParams.set('keyword', value)
        } else {
            newParams.delete('keyword')
        }
        // Reset to page 1 on new search
        newParams.set('page', '1')
        setSearchParams(newParams)
    }

    return (
        <form onSubmit={handleSearch} className="relative w-full max-w-xl">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                    type="text"
                    placeholder="Search for jobs, companies, or keywords..."
                    className="pl-10 pr-10 h-11 bg-white shadow-sm border-slate-200 focus-visible:ring-indigo-500"
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                />
                {keyword && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8 p-0 hover:bg-transparent"
                        onClick={handleClear}
                    >
                        <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
                    </Button>
                )}
            </div>
        </form>
    )
}
