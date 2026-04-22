import { Badge } from '@/components/ui/badge';
import { STATUS_PALETTE } from '@/features/applications/statusPalette';
import type { ApplicationStatus } from '@/types/application';
import { cn } from '@/utils/cn';

interface ApplicationStatusBadgeProps {
    status: ApplicationStatus;
    className?: string;
}

const STATUS_LABEL: Record<ApplicationStatus, string> = {
    PENDING: 'Pending',
    TAILORING: 'Tailoring',
    READY: 'Ready',
    APPLIED: 'Applied',
    PHONE_SCREEN: 'Phone Screen',
    INTERVIEWING: 'Interviewing',
    OFFER: 'Offer',
    REJECTED: 'Rejected',
    FAILED: 'Failed',
};

export type ApplicationStatusPresentation = {
    label: string;
    badgeClass: string;
};

export function getApplicationStatusPresentation(status: ApplicationStatus): ApplicationStatusPresentation {
    const palette = STATUS_PALETTE[status];
    return {
        label: STATUS_LABEL[status] ?? status ?? 'Unknown',
        badgeClass: cn(palette?.badgeClass, palette?.badgeExtraClass),
    };
}

export function ApplicationStatusBadge({ status, className }: ApplicationStatusBadgeProps) {
    const { label, badgeClass } = getApplicationStatusPresentation(status);

    return <Badge className={cn(badgeClass, className)}>{label}</Badge>;
}
