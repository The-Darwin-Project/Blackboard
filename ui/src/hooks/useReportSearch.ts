// BlackBoard/ui/src/hooks/useReportSearch.ts
// @ai-rules:
// 1. [Pattern]: useInfiniteQuery with compound cursor pagination. getNextPageParam returns undefined to stop.
// 2. [Constraint]: Query key includes all filter params so TanStack Query auto-refetches on filter change.
// 3. [Pattern]: Debounced search query is NOT in the hook -- caller debounces before passing q.
import { useInfiniteQuery } from '@tanstack/react-query';
import { searchReports, type ReportSearchParams } from '../api/client';
import type { ReportSearchResponse } from '../api/types';

export interface ReportSearchFilters {
  startTime?: number;
  endTime?: number;
  service?: string;
  source?: string;
  domain?: string;
  severity?: string;
  q?: string;
}

const PAGE_SIZE = 50;

export function useReportSearch(filters: ReportSearchFilters) {
  return useInfiniteQuery<ReportSearchResponse>({
    queryKey: ['reportSearch', filters],
    queryFn: ({ pageParam }) => {
      const params: ReportSearchParams = {
        limit: PAGE_SIZE,
        cursor: pageParam as string | undefined,
        start_time: filters.startTime,
        end_time: filters.endTime,
        service: filters.service,
        source: filters.source,
        domain: filters.domain,
        severity: filters.severity,
        q: filters.q,
      };
      return searchReports(params);
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.has_more ? lastPage.next_cursor ?? undefined : undefined,
    refetchOnWindowFocus: true,
  });
}
