import { Badge } from '@/components/ui/badge';
import type { ApplicationStatus } from '@/types/application';
import { cn } from '@/utils/cn';

interface ApplicationStatusBadgeProps {
    status: ApplicationStatus;
    className?: string;
}

type ApplicationStatusPresentation = {
    label: string;
    className?: string;
    variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success';
};

export function getApplicationStatusPresentation(status: ApplicationStatus): ApplicationStatusPresentation {
    switch (status) {
        case 'PENDING':
            return { label: 'Pending', variant: 'secondary' };
        case 'TAILORING':
            return { label: 'Tailoring', variant: 'secondary', className: 'animate-pulse' };
        case 'READY':
            return { label: 'Ready', className: 'bg-green-500 hover:bg-green-600' };
        case 'APPLIED':
            return { label: 'Applied', variant: 'outline' };
        case 'PHONE_SCREEN':
            return { label: 'Phone Screen', variant: 'outline' };
        case 'INTERVIEWING':
            return { label: 'Interviewing', variant: 'outline' };
        case 'OFFER':
            return { label: 'Offer', className: 'bg-amber-400 text-slate-900 hover:bg-amber-500' };
        case 'REJECTED':
            return { label: 'Rejected', variant: 'secondary' };
        case 'FAILED':
            return { label: 'Failed', className: 'bg-red-500 text-white hover:bg-red-600' };
        default:
            return { label: status || 'Unknown', variant: 'secondary' };
    }
}

export function ApplicationStatusBadge({ status, className }: ApplicationStatusBadgeProps) {
    const presentation = getApplicationStatusPresentation(status);

    return (
        <Badge
            variant={presentation.variant}
            className={cn(presentation.className, className)}
        >
            {presentation.label}
        </Badge>
    );
}
