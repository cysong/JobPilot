import { Badge } from '@/components/ui/badge'
import type { ApplicationResolution } from '@/types/application'

interface ApplicationResolutionBadgeProps {
  resolution: ApplicationResolution
  className?: string
}

export function ApplicationResolutionBadge({
  resolution,
  className,
}: ApplicationResolutionBadgeProps) {
  switch (resolution) {
    case 'ACTIVE':
      return <Badge variant="secondary" className={className}>Active</Badge>
    case 'JOB_CLOSED':
      return <Badge className={`bg-red-500 text-white hover:bg-red-600 ${className}`}>Job Closed</Badge>
    case 'USER_SKIPPED':
      return <Badge variant="outline" className={className}>Skipped</Badge>
    case 'STALE_NO_RESPONSE':
      return <Badge variant="outline" className={className}>No Response</Badge>
    default:
      return <Badge variant="secondary" className={className}>{resolution}</Badge>
  }
}
