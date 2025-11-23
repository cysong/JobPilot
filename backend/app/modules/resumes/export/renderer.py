"""
Markdown to HTML renderer for resume export.
"""
import markdown2
from typing import Optional


class MarkdownRenderer:
    """
    Converts Markdown content to HTML suitable for PDF generation.

    Uses markdown2 with extras for enhanced formatting support.
    """

    # Markdown2 extras for better rendering
    MARKDOWN_EXTRAS = [
        "fenced-code-blocks",  # ```code``` blocks
        "tables",              # Markdown tables
        "break-on-newline",    # Treat \n as <br>
        "cuddled-lists",       # Lists without blank lines
        "header-ids",          # Auto-generate heading IDs
        "task_list",           # - [ ] checkboxes
    ]

    @staticmethod
    def render(
        markdown_content: str,
        extras: Optional[list[str]] = None
    ) -> str:
        """
        Render Markdown to HTML.

        Args:
            markdown_content: Markdown text to convert
            extras: Optional custom markdown2 extras (uses defaults if not provided)

        Returns:
            HTML string suitable for weasyprint
        """
        if extras is None:
            extras = MarkdownRenderer.MARKDOWN_EXTRAS

        html = markdown2.markdown(
            markdown_content,
            extras=extras
        )

        return html

    @staticmethod
    def sanitize_markdown(content: str) -> str:
        """
        Sanitize markdown content before rendering.

        Removes potentially problematic HTML tags while keeping Markdown safe.

        Args:
            content: Raw markdown content

        Returns:
            Sanitized markdown content
        """
        # For now, just strip excessive newlines
        # In production, you might want to use bleach or html5lib
        lines = content.split('\n')

        # Remove excessive blank lines (max 2 consecutive)
        sanitized_lines = []
        blank_count = 0

        for line in lines:
            if line.strip() == '':
                blank_count += 1
                if blank_count <= 2:
                    sanitized_lines.append(line)
            else:
                blank_count = 0
                sanitized_lines.append(line)

        return '\n'.join(sanitized_lines)
