import { useState } from 'react'
import { useSkills, useSkillMutations } from '../hooks/useSkills'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
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
import { RefreshCw, Plus, Edit, Trash2, Tag } from 'lucide-react'
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

export const SkillsManagement = () => {
  const { data, isLoading, error } = useSkills()
  const { deleteSkill, syncSkills } = useSkillMutations()

  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [editingSkill, setEditingSkill] = useState<UserSkill | null>(null)
  const [deletingSkill, setDeletingSkill] = useState<UserSkill | null>(null)

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

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 w-full" />
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
  const manualSkills = skills.filter(s => s.is_manual)
  const autoSkills = skills.filter(s => !s.is_manual)

  return (
    <div className="space-y-6">
      {/* Header with stats */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Tag className="h-5 w-5" />
                My Skills
              </CardTitle>
              <CardDescription>
                Manage your professional skills and proficiency levels
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSync}
                disabled={syncSkills.isPending}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${syncSkills.isPending ? 'animate-spin' : ''}`} />
                Sync from Resumes
              </Button>
              <Button
                size="sm"
                onClick={() => setAddDialogOpen(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Skill
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{data?.total || 0}</p>
              <p className="text-sm text-muted-foreground">Total Skills</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-blue-600">{data?.manual_count || 0}</p>
              <p className="text-sm text-muted-foreground">Manually Added</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{data?.auto_count || 0}</p>
              <p className="text-sm text-muted-foreground">From Resumes</p>
            </div>
          </div>
        </CardContent>
      </Card>

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
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
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
