import { Banknote, Clock, Globe, MapPin, Tag, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import linkedinIcon from "@/assets/source-icons/linkedin.svg";
import seekIcon from "@/assets/source-icons/seek.ico";

type SourceMeta = {
  icon?: LucideIcon;
  iconSrc?: string;
  label: string;
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
): SourceMeta => {
  const raw = source?.trim();
  const normalized = raw?.toLowerCase();
  const label = raw && raw.length > 0 ? raw : "unknown";

  if (normalized === "linkedin") {
    return { iconSrc: linkedinIcon, label };
  }
  if (normalized === "seek") {
    return { iconSrc: seekIcon, label };
  }

  return { icon: Globe, label };
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
  const sourceMeta = getSourceMeta(source);
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
  const sourceMeta = getSourceMeta(job.source);
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
