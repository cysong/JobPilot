import { useState } from 'react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ProficiencyLevel } from '@/types/skill'

interface AddSkillDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const proficiencyOptions = [
  { value: ProficiencyLevel.BEGINNER, label: 'Beginner' },
  { value: ProficiencyLevel.INTERMEDIATE, label: 'Intermediate' },
  { value: ProficiencyLevel.ADVANCED, label: 'Advanced' },
  { value: ProficiencyLevel.EXPERT, label: 'Expert' },
]

export const AddSkillDialog = ({ open, onOpenChange }: AddSkillDialogProps) => {
  const { createSkill } = useSkillMutations()
  const [skillName, setSkillName] = useState('')
  const [proficiency, setProficiency] = useState<ProficiencyLevel>(ProficiencyLevel.INTERMEDIATE)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!skillName.trim()) return

    createSkill.mutate(
      {
        skill_name: skillName.trim(),
        proficiency_level: proficiency,
      },
      {
        onSuccess: () => {
          setSkillName('')
          setProficiency(ProficiencyLevel.INTERMEDIATE)
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
            <DialogTitle>Add New Skill</DialogTitle>
            <DialogDescription>
              Add a new skill to your profile with your proficiency level.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="skill-name">Skill Name</Label>
              <Input
                id="skill-name"
                placeholder="e.g., Python, React, Project Management"
                value={skillName}
                onChange={(e) => setSkillName(e.target.value)}
                autoFocus
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="proficiency">Proficiency Level</Label>
              <Select
                value={proficiency}
                onValueChange={(value) => setProficiency(value as ProficiencyLevel)}
              >
                <SelectTrigger id="proficiency">
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
              disabled={!skillName.trim() || createSkill.isPending}
            >
              {createSkill.isPending ? 'Adding...' : 'Add Skill'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
