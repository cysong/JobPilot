import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'

interface ResumePreviewProps {
    content: string
}

// Custom sanitization schema - allow safe HTML tags but block script
const sanitizeSchema = {
    ...defaultSchema,
    tagNames: [
        ...(defaultSchema.tagNames || []),
        'div', 'span', 'section', 'article', 'header', 'footer', 'nav', 'aside',
        'br', 'hr',
    ],
    attributes: {
        ...defaultSchema.attributes,
        '*': ['className', 'style', 'id'],
    },
}

export function ResumePreview({ content }: ResumePreviewProps) {
    return (
        <div className="prose prose-slate max-w-none bg-white min-h-full p-8">
            <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
                components={{
                    h1: ({ children }) => <h1 className="text-2xl font-bold mb-4 text-slate-900">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-xl font-bold mb-3 mt-6 text-slate-800">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-lg font-semibold mb-2 mt-4 text-slate-800">{children}</h3>,
                    h4: ({ children }) => <h4 className="text-base font-semibold mb-2 mt-3 text-slate-700">{children}</h4>,
                    h5: ({ children }) => <h5 className="text-sm font-semibold mb-1 mt-2 text-slate-700">{children}</h5>,
                    h6: ({ children }) => <h6 className="text-sm font-medium mb-1 mt-2 text-slate-600">{children}</h6>,
                }}
            >
                {content}
            </Markdown>
        </div>
    )
}
