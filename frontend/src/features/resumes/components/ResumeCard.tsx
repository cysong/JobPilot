import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Trash2, Download, Loader2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { ResumeListItem } from '@/types/resume'
import { Button } from '@/components/ui/button'
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
} from "@/components/ui/alert-dialog"
import { resumeApi } from '@/api/resumes'

interface ResumeCardProps {
    resume: ResumeListItem
    onDelete: (id: string) => void
}

export function ResumeCard({ resume, onDelete }: ResumeCardProps) {
    const [isDownloading, setIsDownloading] = useState(false)
    const [isDeleteOpen, setIsDeleteOpen] = useState(false)

    const handleDownload = async (e: React.MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDownloading(true)
        try {
            const blob = await resumeApi.exportResume(resume.id)
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `${resume.title}.pdf`
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)
        } catch (error) {
            console.error('Failed to download resume', error)
        } finally {
            setIsDownloading(false)
        }
    }

    return (
        <Link
            to={`/resumes/${resume.id}`}
            className="block bg-white p-6 rounded-xl shadow-sm border border-slate-200 hover:shadow-md transition-shadow group relative"
        >
            <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-slate-400 hover:text-slate-600"
                    onClick={handleDownload}
                    disabled={isDownloading}
                >
                    {isDownloading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Download className="w-4 h-4" />
                    )}
                </Button>
                <AlertDialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-slate-400 hover:text-red-600"
                        onClick={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            setIsDeleteOpen(true)
                        }}
                    >
                        <Trash2 className="w-4 h-4" />
                    </Button>
                    <AlertDialogContent onClick={(e) => e.stopPropagation()}>
                        <AlertDialogHeader>
                            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                                This action cannot be undone. This will permanently delete your resume.
                            </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                                onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    onDelete(resume.id)
                                    setIsDeleteOpen(false)
                                }}
                                className="bg-red-600 hover:bg-red-700"
                            >
                                Delete
                            </AlertDialogAction>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialog>
            </div>

            <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${resume.is_draft ? 'bg-yellow-50 text-yellow-600' : 'bg-indigo-50 text-indigo-600'
                }`}>
                <FileText className="w-6 h-6" />
            </div>

            <h3 className="font-bold text-slate-900 truncate pr-16">{resume.title}</h3>
            <p className="text-sm text-slate-500 mt-1">
                Updated {formatDistanceToNow(new Date(resume.updated_at), { addSuffix: true })}
            </p>

            {resume.is_draft && (
                <div className="mt-4">
                    <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 font-normal">
                        Draft
                    </Badge>
                </div>
            )}
        </Link>
    )
}
