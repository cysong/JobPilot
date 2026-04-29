/**
 * Frontend-bundled icons for job sources.
 *
 * Keyed by the lowercase `source` value stored in `seek_jobs.source`.
 * Backend provides labels / brand colors via /api/v1/jobs/sources/meta;
 * icons live here so we don't pay for static file hosting on the backend.
 *
 * To add a new source: drop an SVG/ICO under src/assets/source-icons/
 * and register the key here. Backend config (sources.yaml) must also
 * contain a matching entry.
 */
import linkedinIcon from '@/assets/source-icons/linkedin.svg'
import seekIcon from '@/assets/source-icons/seek.ico'
import greenhouseIcon from '@/assets/source-icons/greenhouse.svg'
import glassdoorIcon from '@/assets/source-icons/glassdoor.png'
import workableIcon from '@/assets/source-icons/workable.png'
import smartrecruitersIcon from '@/assets/source-icons/smartrecruiters.png'
import successfactorsCsbIcon from '@/assets/source-icons/successfactors_csb.png'
import pageupJobtoolsIcon from '@/assets/source-icons/pageup_jobtools.png'
import workdayIcon from '@/assets/source-icons/workday.png'

export const SOURCE_ICONS: Record<string, string> = {
  linkedin: linkedinIcon,
  seek: seekIcon,
  greenhouse: greenhouseIcon,
  glassdoor: glassdoorIcon,
  workable: workableIcon,
  smartrecruiters: smartrecruitersIcon,
  successfactors_csb: successfactorsCsbIcon,
  pageup_jobtools: pageupJobtoolsIcon,
  workday: workdayIcon,
}

export const getSourceIcon = (source: string | null | undefined): string | undefined => {
  const key = source?.trim().toLowerCase()
  if (!key) return undefined
  return SOURCE_ICONS[key]
}
