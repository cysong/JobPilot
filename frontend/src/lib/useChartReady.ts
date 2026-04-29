import { useEffect, useRef, useState, type RefObject } from 'react'

/**
 * Returns `[ref, ready]`. `ready` flips to true once the observed element has
 * non-zero width and height. Use it to gate <ResponsiveContainer> so recharts
 * never sees a 0×0 parent on first mount — that's what triggers the
 * "width(-1) and height(-1)" console warning.
 */
export function useChartReady<T extends HTMLElement>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    if (el.clientWidth > 0 && el.clientHeight > 0) {
      setReady(true)
      return
    }

    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) {
        setReady(true)
        ro.disconnect()
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return [ref, ready]
}
