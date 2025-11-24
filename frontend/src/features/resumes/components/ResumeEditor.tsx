import { Textarea } from '@/components/ui/textarea'

interface ResumeEditorProps {
    content: string
    onChange: (value: string) => void
}

export function ResumeEditor({ content, onChange }: ResumeEditorProps) {
    return (
        <Textarea
            value={content}
            onChange={(e) => onChange(e.target.value)}
            className="w-full h-full min-h-[500px] font-mono text-sm p-4 resize-none border-0 focus-visible:ring-0 rounded-none bg-slate-50"
            placeholder="# Your Name\n\n## Experience\n..."
        />
    )
}
