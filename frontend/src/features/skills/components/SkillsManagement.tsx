import { useEffect, useState } from 'react'
import { useSkills, useSkillMutations } from '../hooks/useSkills'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, Plus, Edit, Trash2, Tag, Search } from 'lucide-react'
import type { UserSkill } from '@/types/skill'
import { AddSkillDialog } from './AddSkillDialog'
import { EditSkillDialog } from './EditSkillDialog'

const proficiencyColors = {
  beginner: 'bg-gray-100 text-gray-800',
  intermediate: 'bg-blue-100 text-blue-800',
  advanced: 'bg-green-100 text-green-800',
  expert: 'bg-purple-100 text-purple-800',
}

const proficiencyLabels = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
  expert: 'Expert',
}

const normalizeSkillName = (value: string) => value.trim().toLowerCase()

const isFuzzyMatch = (skillName: string, keyword: string) => {
  const normalizedSkill = normalizeSkillName(skillName)
  const normalizedKeyword = normalizeSkillName(keyword)

  if (!normalizedKeyword) return true
  if (normalizedSkill.includes(normalizedKeyword)) return true

  let keywordIndex = 0
  for (const char of normalizedSkill) {
    if (char === normalizedKeyword[keywordIndex]) {
      keywordIndex += 1
    }

    if (keywordIndex === normalizedKeyword.length) {
      return true
    }
  }

  return false
}

export const SkillsManagement = () => {
  const { data, isLoading, error } = useSkills()
  const { deleteSkill, syncSkills } = useSkillMutations()

  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addDialogInstanceKey, setAddDialogInstanceKey] = useState(0)
  const [addDialogInitialSkillName, setAddDialogInitialSkillName] = useState('')
  const [editingSkill, setEditingSkill] = useState<UserSkill | null>(null)
  const [deletingSkill, setDeletingSkill] = useState<UserSkill | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
    }, 300)

    return () => window.clearTimeout(timeoutId)
  }, [searchInput])

  const handleDelete = () => {
    if (deletingSkill) {
      deleteSkill.mutate(deletingSkill.id, {
        onSuccess: () => setDeletingSkill(null)
      })
    }
  }

  const handleSync = () => {
    syncSkills.mutate()
  }

  const handleOpenAddDialog = (initialSkillName = '') => {
    setAddDialogInitialSkillName(initialSkillName.trim())
    setAddDialogInstanceKey((current) => current + 1)
    setAddDialogOpen(true)
  }

  const handleAddDialogOpenChange = (open: boolean) => {
    setAddDialogOpen(open)

    if (!open) {
      setAddDialogInitialSkillName('')
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-center text-destructive">
            Failed to load skills. Please try again.
          </p>
        </CardContent>
      </Card>
    )
  }

  const skills = data?.items || []
  const filteredSkills = debouncedSearch
    ? skills.filter((skill) => isFuzzyMatch(skill.skill_name, debouncedSearch))
    : skills
  const manualSkills = filteredSkills.filter((s) => s.is_manual)
  const autoSkills = filteredSkills.filter((s) => !s.is_manual)
  const normalizedDebouncedSearch = normalizeSkillName(debouncedSearch)
  const hasExactSkillMatch = normalizedDebouncedSearch
    ? skills.some((skill) => normalizeSkillName(skill.skill_name) === normalizedDebouncedSearch)
    : false
  const showAddFromSearch = Boolean(normalizedDebouncedSearch) && !hasExactSkillMatch

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Skills</h1>
          <p className="mt-1 text-slate-500">
            Manage your professional skills and proficiency levels
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={syncSkills.isPending}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${syncSkills.isPending ? 'animate-spin' : ''}`} />
            Sync from Resumes
          </Button>
          <Button
            size="sm"
            onClick={() => handleOpenAddDialog()}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add Skill
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search skills by name or keyword"
            className="pl-10"
            aria-label="Search skills"
          />
        </div>
        {showAddFromSearch && (
          <Button
            type="button"
            size="sm"
            className="shrink-0"
            onClick={() => handleOpenAddDialog(debouncedSearch)}
          >
            <Plus className="mr-2 h-4 w-4" />
            Add "{debouncedSearch}" as a new skill
          </Button>
        )}
      </div>

      {/* Skills List */}
      <div className="space-y-4">
        {skills.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-muted-foreground">
                <Tag className="h-12 w-12 mx-auto mb-4 opacity-20" />
                <p className="text-lg font-medium">No skills yet</p>
                <p className="text-sm mt-2">
                  Add skills manually or upload a resume to extract them automatically
                </p>
              </div>
            </CardContent>
          </Card>
        ) : filteredSkills.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <div className="text-center text-muted-foreground">
                <Search className="mx-auto mb-4 h-12 w-12 opacity-20" />
                <p className="text-lg font-medium text-slate-900">No matching skills found</p>
                <p className="mt-2 text-sm">
                  Try another keyword or add "{debouncedSearch}" as a new skill.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Manual Skills Section */}
            {manualSkills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-3 flex items-center gap-2">
                  <Plus className="h-4 w-4" />
                  Manually Added Skills ({manualSkills.length})
                </h3>
                <div className="grid gap-3">
                  {manualSkills.map((skill) => (
                    <Card key={skill.id} className="hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium">{skill.skill_name}</h4>
                                <Badge variant="outline" className="text-xs">Manual</Badge>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge className={proficiencyColors[skill.proficiency_level]}>
                              {proficiencyLabels[skill.proficiency_level]}
                            </Badge>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setEditingSkill(skill)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setDeletingSkill(skill)}
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Auto Skills Section */}
            {autoSkills.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-muted-foreground mb-3 flex items-center gap-2">
                  <RefreshCw className="h-4 w-4" />
                  Skills from Resumes ({autoSkills.length})
                </h3>
                <div className="grid gap-3">
                  {autoSkills.map((skill) => (
                    <Card key={skill.id} className="hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <h4 className="font-medium">{skill.skill_name}</h4>
                                <span className="text-xs text-muted-foreground">
                                  ({skill.source_count} resume{skill.source_count > 1 ? 's' : ''})
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge className={proficiencyColors[skill.proficiency_level]}>
                              {proficiencyLabels[skill.proficiency_level]}
                            </Badge>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setEditingSkill(skill)}
                              >
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setDeletingSkill(skill)}
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Dialogs */}
      <AddSkillDialog
        key={addDialogInstanceKey}
        open={addDialogOpen}
        onOpenChange={handleAddDialogOpenChange}
        initialSkillName={addDialogInitialSkillName}
      />

      {editingSkill && (
        <EditSkillDialog
          skill={editingSkill}
          open={!!editingSkill}
          onOpenChange={(open) => !open && setEditingSkill(null)}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deletingSkill} onOpenChange={(open) => !open && setDeletingSkill(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Skill</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletingSkill?.skill_name}"?
              {!deletingSkill?.is_manual && (
                <span className="block mt-2 text-amber-600">
                  Note: This skill will be re-added if it still exists in your resumes during the next sync.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteSkill.isPending}
            >
              {deleteSkill.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
