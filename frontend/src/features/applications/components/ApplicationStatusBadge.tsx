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
    const normalized = status?.toLowerCase?.() || '';

    switch (normalized) {
        case 'pending':
            return { label: 'Pending', variant: 'secondary' };
        case 'tailoring':
            return { label: 'Tailoring', variant: 'secondary', className: 'animate-pulse' };
        case 'ready':
            return { label: 'Ready', className: 'bg-green-500 hover:bg-green-600' };
        case 'applied':
            return { label: 'Applied', variant: 'outline' };
        case 'phonescreen':
            return { label: 'Phone Screen', variant: 'outline' };
        case 'interviewing':
            return { label: 'Interviewing', variant: 'outline' };
        case 'offer':
            return { label: 'Offer', className: 'bg-amber-400 text-slate-900 hover:bg-amber-500' };
        case 'rejected':
            return { label: 'Rejected', variant: 'secondary' };
        case 'failed':
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
