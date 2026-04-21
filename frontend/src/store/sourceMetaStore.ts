/**
 * Source-metadata Zustand store.
 *
 * Fetched once per session (after login) and cached in memory. Components
 * look up per-source metadata synchronously via `getSourceMetaByKey(key)`;
 * when the key is unknown or the fetch has not resolved yet, `undefined`
 * is returned and callers should fall back to sensible defaults.
 */
import { create } from 'zustand'
import { sourceMetaApi } from '@/api/sourceMeta'
import type { SourceMeta } from '@/types/sourceMeta'

type FetchStatus = 'idle' | 'loading' | 'ready' | 'error'

interface SourceMetaState {
  metas: SourceMeta[]
  byKey: Record<string, SourceMeta>
  status: FetchStatus
  error: string | null

  fetchIfNeeded: () => Promise<void>
  reload: () => Promise<void>
  reset: () => void
}

const buildIndex = (list: SourceMeta[]): Record<string, SourceMeta> => {
  const index: Record<string, SourceMeta> = {}
  for (const meta of list) {
    index[meta.key.toLowerCase()] = meta
  }
  return index
}

let inflight: Promise<void> | null = null

export const useSourceMetaStore = create<SourceMetaState>()((set, get) => ({
  metas: [],
  byKey: {},
  status: 'idle',
  error: null,

  fetchIfNeeded: async () => {
    const { status } = get()
    if (status === 'ready' || status === 'loading') {
      if (inflight) return inflight
      return
    }
    return get().reload()
  },

  reload: async () => {
    if (inflight) return inflight
    set({ status: 'loading', error: null })
    inflight = (async () => {
      try {
        const list = await sourceMetaApi.list()
        set({
          metas: list,
          byKey: buildIndex(list),
          status: 'ready',
          error: null,
        })
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        set({ status: 'error', error: message })
      } finally {
        inflight = null
      }
    })()
    return inflight
  },

  reset: () => {
    inflight = null
    set({ metas: [], byKey: {}, status: 'idle', error: null })
  },
}))

/**
 * Synchronous lookup helper. Returns undefined for unknown keys so callers
 * can decide their own fallback (icon / label).
 */
export const getSourceMetaByKey = (source: string | null | undefined): SourceMeta | undefined => {
  const key = source?.trim().toLowerCase()
  if (!key) return undefined
  return useSourceMetaStore.getState().byKey[key]
}
