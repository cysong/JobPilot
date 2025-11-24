import Markdown from 'react-markdown'

interface ResumePreviewProps {
    content: string
}

export function ResumePreview({ content }: ResumePreviewProps) {
    return (
        <div className="prose prose-slate max-w-none p-8 bg-white min-h-full shadow-sm">
            <Markdown>{content}</Markdown>
        </div>
    )
}
