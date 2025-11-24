import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { ArrowLeft, Save, FileCheck, Download } from 'lucide-react'
import { useResume, useResumeMutations } from '@/features/resumes/hooks/useResumes'
import { ResumeEditor } from '@/features/resumes/components/ResumeEditor'
import { ResumePreview } from '@/features/resumes/components/ResumePreview'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Form, FormControl, FormField, FormItem, FormMessage } from '@/components/ui/form'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { resumeApi } from '@/api/resumes'

const formSchema = z.object({
    title: z.string().min(1, 'Title is required'),
    content: z.string(),
})

export default function ResumeEditPage() {
    const { id } = useParams()
    const isNew = !id || id === 'new'
    const navigate = useNavigate()
    const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit')

    const { data: resume, isLoading } = useResume(isNew ? '' : id!)
    const { createResume, updateResume, finalizeResume } = useResumeMutations()

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            title: '',
            content: '',
        },
    })

    // Load data when resume is fetched
    useEffect(() => {
        if (resume) {
            form.reset({
                title: resume.title,
                content: resume.content,
            })
        }
    }, [resume, form])

    const onSubmit = (values: z.infer<typeof formSchema>) => {
        if (isNew) {
            createResume.mutate({ ...values, is_draft: true })
        } else {
            updateResume.mutate({ id: id!, data: values })
        }
    }

    const handleFinalize = () => {
        if (!isNew && id) {
            finalizeResume.mutate(id)
        }
    }

    const handleDownload = async () => {
        if (!isNew && id && resume) {
            try {
                const blob = await resumeApi.exportResume(id)
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
            }
        }
    }

    if (isLoading && !isNew) {
        return <div className="p-8 space-y-4">
            <Skeleton className="h-8 w-1/3" />
            <Skeleton className="h-[600px] w-full" />
        </div>
    }

    return (
        <div className="h-[calc(100vh-4rem)] flex flex-col">
            {/* Header */}
            <div className="bg-white border-b border-slate-200 px-6 py-3 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => navigate('/resumes')}>
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <Form {...form}>
                        <form className="flex items-center gap-2">
                            <FormField
                                control={form.control}
                                name="title"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormControl>
                                            <Input
                                                {...field}
                                                placeholder="Resume Title"
                                                className="text-lg font-semibold border-transparent hover:border-slate-200 focus:border-indigo-500 w-[300px]"
                                            />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />
                        </form>
                    </Form>
                    {!isNew && resume?.is_draft && (
                        <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">Draft</Badge>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <div className="bg-slate-100 p-1 rounded-lg flex text-sm font-medium text-slate-600 mr-4">
                        <button
                            onClick={() => setActiveTab('edit')}
                            className={`px-3 py-1.5 rounded-md transition-all ${activeTab === 'edit' ? 'bg-white text-slate-900 shadow-sm' : 'hover:text-slate-900'}`}
                        >
                            Edit
                        </button>
                        <button
                            onClick={() => setActiveTab('preview')}
                            className={`px-3 py-1.5 rounded-md transition-all ${activeTab === 'preview' ? 'bg-white text-slate-900 shadow-sm' : 'hover:text-slate-900'}`}
                        >
                            Preview
                        </button>
                    </div>

                    {!isNew && !resume?.is_draft && (
                        <Button variant="outline" onClick={handleDownload}>
                            <Download className="w-4 h-4 mr-2" />
                            Export PDF
                        </Button>
                    )}

                    {!isNew && resume?.is_draft && (
                        <Button variant="outline" onClick={handleFinalize} className="text-indigo-600 border-indigo-200 hover:bg-indigo-50">
                            <FileCheck className="w-4 h-4 mr-2" />
                            Finalize
                        </Button>
                    )}

                    <Button onClick={form.handleSubmit(onSubmit)} disabled={!form.formState.isDirty}>
                        <Save className="w-4 h-4 mr-2" />
                        Save
                    </Button>
                </div>
            </div>

            {/* Editor/Preview Area */}
            <div className="flex-1 overflow-hidden bg-slate-50">
                {activeTab === 'edit' ? (
                    <div className="h-full flex">
                        <div className="w-1/2 h-full border-r border-slate-200 bg-white">
                            <FormField
                                control={form.control}
                                name="content"
                                render={({ field }) => (
                                    <ResumeEditor content={field.value} onChange={field.onChange} />
                                )}
                            />
                        </div>
                        <div className="w-1/2 h-full overflow-auto bg-slate-50 p-8">
                            <div className="bg-white shadow-sm min-h-[800px] p-8">
                                <ResumePreview content={form.watch('content')} />
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="h-full overflow-auto p-8 flex justify-center">
                        <div className="w-full max-w-4xl bg-white shadow-lg min-h-[1000px]">
                            <ResumePreview content={form.watch('content')} />
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
