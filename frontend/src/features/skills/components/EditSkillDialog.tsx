import { useState, useEffect } from 'react'
import { useSkillMutations } from '../hooks/useSkills'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ProficiencyLevel, type UserSkill } from '@/types/skill'

interface EditSkillDialogProps {
  skill: UserSkill
  open: boolean
  onOpenChange: (open: boolean) => void
}

const proficiencyOptions = [
  { value: ProficiencyLevel.BEGINNER, label: 'Beginner' },
  { value: ProficiencyLevel.INTERMEDIATE, label: 'Intermediate' },
  { value: ProficiencyLevel.ADVANCED, label: 'Advanced' },
  { value: ProficiencyLevel.EXPERT, label: 'Expert' },
]

export const EditSkillDialog = ({ skill, open, onOpenChange }: EditSkillDialogProps) => {
  const { updateSkill } = useSkillMutations()
  const [proficiency, setProficiency] = useState<ProficiencyLevel>(skill.proficiency_level)

  // Update proficiency when skill changes
  useEffect(() => {
    setProficiency(skill.proficiency_level)
  }, [skill])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    updateSkill.mutate(
      {
        skillId: skill.id,
        data: { proficiency_level: proficiency },
      },
      {
        onSuccess: () => {
          onOpenChange(false)
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Skill</DialogTitle>
            <DialogDescription>
              Update the proficiency level for "{skill.skill_name}".
              {!skill.is_manual && (
                <span className="block mt-2 text-amber-600 text-sm">
                  This skill was extracted from your resume. Editing it will mark it as manually managed.
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="skill-name-display">Skill Name</Label>
              <div className="px-3 py-2 bg-muted rounded-md text-sm">
                {skill.skill_name}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-proficiency">Proficiency Level</Label>
              <Select
                value={proficiency}
                onValueChange={(value) => setProficiency(value as ProficiencyLevel)}
              >
                <SelectTrigger id="edit-proficiency">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {proficiencyOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={updateSkill.isPending || proficiency === skill.proficiency_level}
            >
              {updateSkill.isPending ? 'Updating...' : 'Update Skill'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
