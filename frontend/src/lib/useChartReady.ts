import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Returns `[ref, ready]`. `ready` flips to true once the observed element has
 * non-zero width and height. Use it to gate <ResponsiveContainer> so recharts
 * never sees a 0×0 parent on first mount — that's what triggers the
 * "width(-1) and height(-1)" console warning.
 *
 * Uses a callback ref so the observer is attached the moment the element
 * mounts, even if the element is rendered conditionally after the hook
 * itself has already mounted (e.g. behind an isLoading early return).
 */
export function useChartReady<T extends HTMLElement>(): [
  (node: T | null) => void,
  boolean,
] {
  const [ready, setReady] = useState(false)
  const observerRef = useRef<ResizeObserver | null>(null)

  useEffect(() => {
    return () => {
      observerRef.current?.disconnect()
      observerRef.current = null
    }
  }, [])

  const refCallback = useCallback((node: T | null) => {
    observerRef.current?.disconnect()
    observerRef.current = null

    if (!node) return

    if (node.clientWidth > 0 && node.clientHeight > 0) {
      setReady(true)
      return
    }

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) {
        setReady(true)
        ro.disconnect()
        observerRef.current = null
      }
    })
    ro.observe(node)
    observerRef.current = ro
  }, [])

  return [refCallback, ready]
}
