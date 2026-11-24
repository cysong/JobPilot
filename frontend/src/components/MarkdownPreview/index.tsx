import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import type { MarkdownPreviewVariant } from './variant'
import { cn } from '@/utils/cn'
import './styles.css'

interface MarkdownPreviewProps {
  content: string
  variant?: MarkdownPreviewVariant
}

const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    'div',
    'span',
    'section',
    'article',
    'header',
    'footer',
    'nav',
    'aside',
    'br',
    'hr',
  ],
  attributes: {
    ...defaultSchema.attributes,
    '*': ['className', 'style', 'id'],
  },
}

const proseHeadings: Components = {
  h1: ({ children }) => <h1 className="text-2xl font-bold mb-4">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-bold mb-3 mt-6">{children}</h2>,
  h3: ({ children }) => <h3 className="text-lg font-semibold mb-2 mt-4">{children}</h3>,
}

export function MarkdownPreview({ content, variant = 'default' }: MarkdownPreviewProps) {
  const isResume = variant === 'resume'
  return (
    <div className={cn('min-h-full', isResume ? 'resume-preview' : 'prose prose-slate max-w-none p-8')}>
      <Markdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, sanitizeSchema]]}
        components={isResume ? undefined : proseHeadings}
      >
        {content}
      </Markdown>
    </div>
  )
}

