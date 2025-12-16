import { useQuery } from '@tanstack/react-query';
import { applicationApi } from '@/api/applications';

/**
 * Hook to fetch application for a specific job
 * Returns null if no application exists for this job
 */
export function useApplicationByJob(jobId: number) {
    return useQuery({
        queryKey: ['application', 'by-job', jobId],
        queryFn: () => applicationApi.getByJobId(jobId),
        retry: false, // Don't retry on 404
        staleTime: 30000, // Consider data fresh for 30 seconds
    });
}
