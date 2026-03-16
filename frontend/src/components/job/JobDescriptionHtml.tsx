type JobDescriptionHtmlProps = {
  html: string | null | undefined;
  emptyText?: string;
};

export function JobDescriptionHtml({
  html,
  emptyText = "No description available.",
}: JobDescriptionHtmlProps) {
  return (
    <div
      className="prose prose-slate max-w-none 
        prose-headings:font-bold prose-headings:text-slate-900 prose-headings:mb-3 prose-headings:mt-8 first:prose-headings:mt-0 prose-headings:tracking-tight
        prose-h3:text-lg 
        prose-p:text-slate-700 prose-p:leading-relaxed prose-p:mb-4
        prose-li:text-slate-700 prose-li:marker:text-slate-500 prose-li:my-0.5
        [&_li_p]:m-0
        prose-ul:my-4 prose-ul:mb-6
        prose-strong:font-bold prose-strong:text-slate-900
        prose-a:text-indigo-600 prose-a:font-medium prose-a:no-underline hover:prose-a:underline"
      dangerouslySetInnerHTML={{
        __html: html || `<p>${emptyText}</p>`,
      }}
    />
  );
}
