import { ChevronDown, Download, Loader2, RefreshCw } from 'lucide-react'

import { ApplicationResolutionBadge } from '@/features/applications/components/ApplicationResolutionBadge'
import { ApplicationStatusBadge } from '@/features/applications/components/ApplicationStatusBadge'
import { getApplicationMaterialStateClassName } from '@/features/applications/presentation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import type { Application, ApplicationResolution, ApplicationStatus } from '@/types/application'
import { cn } from '@/utils/cn'

export type ApplicationStatusAction = {
  label: string
  nextStatus: ApplicationStatus
  variant?: 'default' | 'outline'
}

type ApplicationOperationsCardProps = {
  application: Application
  statusDescription: string
  isInactiveResolution: boolean
  isTailoring: boolean
  primaryAction: ApplicationStatusAction | null
  secondaryStatusActions: ApplicationStatusAction[]
  canResolveApplication: boolean
  resumeMaterialState: 'Pending' | 'Generating' | 'Ready' | 'Failed'
  coverLetterMaterialState: 'Pending' | 'Generating' | 'Ready' | 'Failed'
  isDownloadingResume: boolean
  isDownloadingCoverLetter: boolean
  retryVisible: boolean
  isUpdateStatusPending: boolean
  isUpdateResolutionPending: boolean
  isRetryPending: boolean
  onStatusUpdate: (status: ApplicationStatus) => void
  onResolutionUpdate: (resolution: ApplicationResolution) => void
  onDownloadResumePdf: () => void
  onDownloadCoverLetterPdf: () => void
  onOpenRetryDialog: () => void
}

export function ApplicationOperationsCard({
  application,
  statusDescription,
  isInactiveResolution,
  isTailoring,
  primaryAction,
  secondaryStatusActions,
  canResolveApplication,
  resumeMaterialState,
  coverLetterMaterialState,
  isDownloadingResume,
  isDownloadingCoverLetter,
  retryVisible,
  isUpdateStatusPending,
  isUpdateResolutionPending,
  isRetryPending,
  onStatusUpdate,
  onResolutionUpdate,
  onDownloadResumePdf,
  onDownloadCoverLetterPdf,
  onOpenRetryDialog,
}: ApplicationOperationsCardProps) {
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Operations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <ApplicationStatusBadge status={application.status} />
          {application.resolution !== 'ACTIVE' && (
            <ApplicationResolutionBadge resolution={application.resolution} />
          )}
        </div>
        {(() => {
          const hasSecondaryStatus = !isInactiveResolution && secondaryStatusActions.length > 0
          const hasResolutionItems = canResolveApplication && !isInactiveResolution
          const showSecondary = hasSecondaryStatus || hasResolutionItems
          const primaryVariant: 'default' | 'outline' = isInactiveResolution
            ? 'default'
            : primaryAction
              ? primaryAction.variant || 'default'
              : 'default'

          return (
            <div className="flex">
              {isInactiveResolution ? (
                <Button
                  className={cn('flex-1', showSecondary && 'rounded-r-none')}
                  onClick={() => onResolutionUpdate('ACTIVE')}
                  disabled={isUpdateResolutionPending}
                >
                  {isUpdateResolutionPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Mark as Active
                </Button>
              ) : primaryAction ? (
                <Button
                  className={cn('flex-1', showSecondary && 'rounded-r-none')}
                  variant={primaryAction.variant || 'default'}
                  onClick={() => onStatusUpdate(primaryAction.nextStatus)}
                  disabled={isUpdateStatusPending}
                >
                  {isUpdateStatusPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {primaryAction.label}
                </Button>
              ) : (
                <Button className={cn('flex-1', showSecondary && 'rounded-r-none')} disabled>
                  {isTailoring ? 'Generating Materials' : 'No Primary Action'}
                </Button>
              )}

              {showSecondary && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant={primaryVariant}
                      className={cn(
                        'rounded-l-none px-2',
                        primaryVariant === 'default' && 'border-l border-l-black/15',
                      )}
                      disabled={isUpdateStatusPending || isUpdateResolutionPending}
                      aria-label="More actions"
                    >
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    {hasSecondaryStatus &&
                      secondaryStatusActions.map((action) => (
                        <DropdownMenuItem
                          key={action.nextStatus}
                          onClick={() => onStatusUpdate(action.nextStatus)}
                          disabled={isUpdateStatusPending}
                        >
                          {action.label}
                        </DropdownMenuItem>
                      ))}
                    {hasResolutionItems && (
                      <>
                        <DropdownMenuItem
                          onClick={() => onResolutionUpdate('USER_SKIPPED')}
                          disabled={isUpdateResolutionPending}
                        >
                          Skip Application
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => onResolutionUpdate('JOB_CLOSED')}
                          disabled={isUpdateResolutionPending}
                          className="text-red-700 focus:text-red-700"
                        >
                          Mark as Job Closed
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          )
        })()}
        <p className="text-sm text-slate-600">{statusDescription}</p>
        <Separator />
        <div className="space-y-2">
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-900">Resume</div>
            </div>
            <div
              className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${getApplicationMaterialStateClassName(
                resumeMaterialState,
              )}`}
            >
              {resumeMaterialState}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={onDownloadResumePdf}
              disabled={!application.resume_document_id || isDownloadingResume}
            >
              {isDownloadingResume ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              PDF
            </Button>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-900">Cover Letter</div>
            </div>
            <div
              className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${getApplicationMaterialStateClassName(
                coverLetterMaterialState,
              )}`}
            >
              {coverLetterMaterialState}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={onDownloadCoverLetterPdf}
              disabled={!application.cover_letter_document_id || isDownloadingCoverLetter}
            >
              {isDownloadingCoverLetter ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              PDF
            </Button>
          </div>
        </div>
        {retryVisible && (
          <Button
            variant="outline"
            className="w-full justify-start"
            onClick={onOpenRetryDialog}
            disabled={isRetryPending}
          >
            <RefreshCw className={cn('mr-2 h-4 w-4', isRetryPending && 'animate-spin')} />
            Retry Generation
          </Button>
        )}
        {isTailoring && (
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700">
            Materials are generating. Retry is unavailable until processing completes.
          </div>
        )}
      </CardContent>
    </Card>
  )
}
