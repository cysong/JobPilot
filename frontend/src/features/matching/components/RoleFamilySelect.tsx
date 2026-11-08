import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useRoleFamilies, useSetResumeRoleFamily } from '@/features/matching/hooks/useMatching'

const NONE = 'none'

interface RoleFamilySelectProps {
  resumeId: string
  value: string | null
}

/** Pick the role family a formal resume is matched against (one per resume). */
export function RoleFamilySelect({ resumeId, value }: RoleFamilySelectProps) {
  const { data: families = [] } = useRoleFamilies()
  const setFamily = useSetResumeRoleFamily()

  return (
    <div className="mt-3 space-y-1">
      <span className="text-xs font-medium text-slate-500">Matched as</span>
      <Select
        value={value ?? NONE}
        disabled={setFamily.isPending}
        onValueChange={(next) =>
          setFamily.mutate({ resumeId, roleFamily: next === NONE ? null : next })
        }
      >
        <SelectTrigger className="h-8 text-sm">
          <SelectValue placeholder="Select a role family" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE}>Not used for matching</SelectItem>
          {families.map((family) => (
            <SelectItem key={family.key} value={family.key}>
              {family.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
