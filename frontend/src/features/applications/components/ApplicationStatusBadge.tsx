import { Badge } from '@/components/ui/badge';
import type { ApplicationStatus } from '@/types/application';

interface ApplicationStatusBadgeProps {
    status: ApplicationStatus;
    className?: string;
}

export function ApplicationStatusBadge({ status, className }: ApplicationStatusBadgeProps) {
    const normalized = status?.toLowerCase?.() || '';

    switch (normalized) {
        case 'pending':
            return <Badge variant="secondary" className={className}>Pending</Badge>;
        case 'tailoring':
            return <Badge variant="secondary" className={`animate-pulse ${className}`}>Tailoring</Badge>;
        case 'ready':
            return <Badge className={`bg-green-500 hover:bg-green-600 ${className}`}>Ready</Badge>;
        case 'applied':
            return <Badge variant="outline" className={className}>Applied</Badge>;
        case 'phonescreen':
            return <Badge variant="outline" className={className}>Phone Screen</Badge>;
        case 'interviewing':
            return <Badge variant="outline" className={className}>Interviewing</Badge>;
        case 'offer':
            return <Badge className={`bg-amber-400 text-slate-900 hover:bg-amber-500 ${className}`}>Offer</Badge>;
        case 'rejected':
            return <Badge variant="secondary" className={className}>Rejected</Badge>;
        case 'failed':
            return <Badge className={`bg-red-500 text-white hover:bg-red-600 ${className}`}>Failed</Badge>;
        default:
            return <Badge variant="secondary" className={className}>{status || 'Unknown'}</Badge>;
    }
}
