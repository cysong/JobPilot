/**
 * Turn a FastAPI error `detail` into display text.
 *
 * `detail` is a string for HTTPException but a list of
 * `{ loc, msg, type }` objects for request validation errors (422);
 * rendering the list directly crashes React.
 */
export const formatErrorDetail = (detail: unknown): string | null => {
  if (typeof detail === 'string') return detail || null
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : null,
      )
      .filter((msg): msg is string => Boolean(msg))
    return messages.length > 0 ? messages.join('; ') : null
  }
  return null
}
