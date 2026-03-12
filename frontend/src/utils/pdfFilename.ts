const sanitizeFilenamePart = (value: string, fallback = ''): string => {
  const cleaned = value
    .trim()
    .replace(/[^A-Za-z0-9]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
  return cleaned || fallback
}

export const buildApplicationPdfFilename = (params: {
  userName?: string | null
  label: string
  jobTitle?: string | null
}): string => {
  const userPart = sanitizeFilenamePart(params.userName || '', 'User')
  const labelPart = sanitizeFilenamePart(params.label)
  const jobPart = sanitizeFilenamePart(params.jobTitle || '', 'Job')

  const parts = [userPart]
  if (labelPart) {
    parts.push(labelPart)
  }
  parts.push(jobPart)

  return `${parts.join('_')}.pdf`
}

