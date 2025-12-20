import { Textarea } from '@/components/ui/textarea'

interface MarkdownEditorProps {
  content: string
  onChange: (value: string) => void
}

export function MarkdownEditor({ content, onChange }: MarkdownEditorProps) {
  return (
    <Textarea
      value={content}
      onChange={(e) => onChange(e.target.value)}
      className="w-full h-full min-h-[500px] font-mono text-sm p-8 resize-none border-0 focus-visible:ring-0 rounded-none bg-transparent"
      placeholder="# Start writing here..."
    />
  )
}
