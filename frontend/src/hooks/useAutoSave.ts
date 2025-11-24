import { useEffect, useCallback } from 'react'
import { useToast } from '@/components/ui/use-toast'

interface UseAutoSaveProps<T> {
    data: T
    onSave: (data: T) => void
    interval?: number
    enabled?: boolean
    storageKey?: string
}

export function useAutoSave<T>({
    data,
    onSave,
    interval = 5000,
    enabled = true,
    storageKey
}: UseAutoSaveProps<T>) {
    const { toast } = useToast()

    const saveToStorage = useCallback((dataToSave: T) => {
        if (storageKey) {
            localStorage.setItem(storageKey, JSON.stringify({
                ...dataToSave,
                savedAt: new Date().toISOString()
            }))
        }
    }, [storageKey])

    useEffect(() => {
        if (!enabled) return

        const timer = setTimeout(() => {
            onSave(data)
            if (storageKey) {
                saveToStorage(data)
            }
        }, interval)

        return () => clearTimeout(timer)
    }, [data, enabled, interval, onSave, saveToStorage, storageKey])

    return {
        saveToStorage
    }
}
