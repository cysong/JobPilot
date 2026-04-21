import { Banknote, Clock, Globe, MapPin, Tag, type LucideIcon } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { getSourceIcon } from "@/config/sourceIcons";
import { getSourceMetaByKey, useSourceMetaStore } from "@/store/sourceMetaStore";

/**
 * UI-ready rendering info for a job source. Label / brand color come from
 * the backend (/api/v1/jobs/sources/meta, cached in sourceMetaStore) while
 * the icon asset is resolved from the frontend bundle via sourceIcons.ts.
 * When the key is unknown or metadata has not loaded yet, we fall back to
 * the raw string + a generic globe icon so the UI always renders.
 */
type SourceDisplay = {
  icon?: LucideIcon;
  iconSrc?: string;
  label: string;
  brandColor?: string | null;
};

type JobDisplayFields = {
  source?: string | null;
  location_label?: string | null;
  work_types_label?: string | null;
  salary_label?: string | null;
  classification?: string | null;
  sub_classification?: string | null;
};

export const getSourceMeta = (
  source: string | null | undefined,
): SourceDisplay => {
  const raw = source?.trim();
  const iconSrc = getSourceIcon(raw);
  const meta = getSourceMetaByKey(raw);

  const label =
    meta?.label ?? (raw && raw.length > 0 ? raw : "unknown");

  if (iconSrc) {
    return { iconSrc, label, brandColor: meta?.brand_color ?? null };
  }
  return { icon: Globe, label, brandColor: meta?.brand_color ?? null };
};

/**
 * React-aware variant. Two responsibilities:
 *   1. Lazily trigger the source-meta fetch the first time any component
 *      actually needs it (post-login prefetch was wasteful for users who
 *      never open a job view). `fetchIfNeeded` is idempotent and dedupes
 *      concurrent calls via an `inflight` promise, so every card mounting
 *      at once still results in a single request. When a prior fetch
 *      ended in `error`, the next mount naturally retries.
 *   2. Subscribe to the store so the label / brand color update once the
 *      async fetch resolves (avoids a frozen Globe fallback).
 *
 * Pure helpers outside React (e.g. chart data builders) should use
 * `getSourceMeta` and accept whatever is cached at call time.
 */
export const useSourceDisplay = (
  source: string | null | undefined,
): SourceDisplay => {
  // Subscribe so the label/brandColor update once the store resolves.
  useSourceMetaStore((state) => state.byKey);
  const fetchIfNeeded = useSourceMetaStore((state) => state.fetchIfNeeded);
  useEffect(() => {
    void fetchIfNeeded();
  }, [fetchIfNeeded]);
  return getSourceMeta(source);
};

export const getCompanyDisplayName = (
  companyName: string | null | undefined,
  advertiserName: string | null | undefined,
): string => advertiserName?.trim() || companyName?.trim() || "Unknown company";

export const formatJobCategory = ({
  classification,
  sub_classification,
}: Pick<JobDisplayFields, "classification" | "sub_classification">): string | null => {
  const parent = classification?.trim();
  const child = sub_classification?.trim();

  if (child && parent) return `${child} (${parent})`;
  if (child) return child;
  if (parent) return parent;
  return null;
};

type JobAttributeListProps = {
  job: JobDisplayFields;
  className?: string;
  showSource?: boolean;
  showCategory?: boolean;
  showSalary?: boolean;
};

type JobSourceCompanyLineProps = {
  source?: string | null;
  companyName?: string | null;
  advertiserName?: string | null;
  className?: string;
  iconClassName?: string;
};

export function JobSourceCompanyLine({
  source,
  companyName,
  advertiserName,
  className,
  iconClassName,
}: JobSourceCompanyLineProps) {
  const sourceMeta = useSourceDisplay(source);
  const SourceIcon = sourceMeta.icon;
  const companyDisplay = getCompanyDisplayName(companyName, advertiserName);

  return (
    <div className={`flex items-center gap-2 text-slate-600 ${className ?? ""}`.trim()}>
      {sourceMeta.iconSrc ? (
        <img
          src={sourceMeta.iconSrc}
          alt={`${sourceMeta.label} icon`}
          className={`${iconClassName ?? "h-5 w-5"} rounded-sm object-contain`.trim()}
        />
      ) : (
        SourceIcon && <SourceIcon className={iconClassName ?? "h-5 w-5"} />
      )}
      <span className="text-slate-500">{sourceMeta.label}</span>
      <span className="text-slate-300">|</span>
      <span className="font-medium">{companyDisplay}</span>
    </div>
  );
}

type JobSalaryDisplayProps = {
  salaryLabel?: string | null;
  className?: string;
  iconClassName?: string;
};

export function JobSalaryDisplay({
  salaryLabel,
  className,
  iconClassName,
}: JobSalaryDisplayProps) {
  if (!salaryLabel) return null;

  return (
      <div className={`flex items-center gap-1.5 ${className ?? ""}`.trim()}>
      <Banknote className={iconClassName ?? "h-3.5 w-3.5"} />
      <span>{salaryLabel}</span>
    </div>
  );
}

export function JobAttributeList({
  job,
  className,
  showSource = false,
  showCategory = true,
  showSalary = false,
}: JobAttributeListProps) {
  const sourceMeta = useSourceDisplay(job.source);
  const SourceIcon = sourceMeta.icon;
  const category = formatJobCategory(job);

  const items = [
    showSource
      ? {
          key: "source",
          icon: sourceMeta.iconSrc ? null : SourceIcon,
          iconSrc: sourceMeta.iconSrc,
          label: sourceMeta.label,
        }
      : null,
    job.location_label
      ? { key: "location", icon: MapPin, label: job.location_label }
      : null,
    job.work_types_label
      ? { key: "type", icon: Clock, label: job.work_types_label }
      : null,
    showSalary && job.salary_label
      ? {
          key: "salary",
          content: <JobSalaryDisplay salaryLabel={job.salary_label} />,
        }
      : null,
    showCategory && category
      ? { key: "category", icon: Tag, label: category }
      : null,
  ].filter(Boolean) as Array<{
    key: string;
    icon?: LucideIcon | null;
    iconSrc?: string;
    label?: string;
    content?: ReactNode;
  }>;

  if (items.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 ${className ?? ""}`.trim()}>
      {items.map((item) => (
        <div key={item.key} className="flex items-center gap-1.5">
          {item.content ? (
            item.content
          ) : (
            <>
              {item.iconSrc ? (
                <img
                  src={item.iconSrc}
                  alt={`${item.label} icon`}
                  className="h-3.5 w-3.5 rounded-sm object-contain"
                />
              ) : item.icon ? (
                <item.icon className="h-3.5 w-3.5" />
              ) : null}
              <span>{item.label}</span>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
