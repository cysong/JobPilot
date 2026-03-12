"""
PDF generator using weasyprint.
Supports multiple document types (resume, cover_letter, etc.)
"""
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import os

if os.name == 'nt':
    try:
        # On Windows, we need to explicitly add the GTK3 bin directory to the DLL search path
        # even if it's already in the PATH environment variable (for Python 3.8+).
        path_env = os.environ.get('PATH', '')
        for path in path_env.split(os.pathsep):
            path = path.strip()
            if path and os.path.isdir(path):
                # Look for the specific DLL that causes the 0x7e error if missing
                if any(f.lower() == 'libgobject-2.0-0.dll' for f in os.listdir(path)):
                    os.add_dll_directory(path)
                    break
    except Exception:
        # If something goes wrong (e.g. permission error), we continue and hope for the best
        pass

from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.core.config import settings
from .renderer import MarkdownRenderer


class PDFGenerator:
    """
    Generates PDF from Markdown content using weasyprint.

    Features:
    - Multiple document types (resume, cover_letter)
    - Template-based rendering (Jinja2)
    - Custom CSS styling per document type and template
    - Chinese font support
    - Metadata embedding
    """

    # Paths
    TEMPLATES_DIR = Path(__file__).parent / "templates"
    STATIC_DIR = Path(__file__).parent.parent / "static"
    CSS_DIR = STATIC_DIR / "css"
    FONTS_DIR = STATIC_DIR / "fonts"

    def __init__(
        self,
        document_type: str,
        template_name: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False
    ):
        """
        Initialize PDF generator.

        Args:
            document_type: Type of document (resume, cover_letter, etc.)
            template_name: Template to use (modern/classic/minimal)
            font_size: Base font size in pt
            include_metadata: Whether to include creation date footer
        """
        self.document_type = document_type
        self.template_name = template_name or settings.EXPORT_DEFAULT_TEMPLATE
        self.font_size = font_size
        self.include_metadata = include_metadata

        # Validate document type
        available_types = self.get_available_document_types()
        if document_type not in available_types:
            raise ValueError(
                f"Invalid document_type '{document_type}'. "
                f"Available: {available_types}"
            )

        # Validate template for this document type
        available_templates = self.get_available_templates(document_type)
        if self.template_name not in available_templates:
            raise ValueError(
                f"Invalid template '{self.template_name}' for document_type '{document_type}'. "
                f"Available: {available_templates}"
            )

        # Setup Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATES_DIR)),
            autoescape=True
        )

    def generate(
        self,
        markdown_content: str,
        title: str,
        output_path: Optional[Path] = None,
        language: str = "en"
    ) -> bytes:
        """
        Generate PDF from Markdown content.

        Args:
            markdown_content: Document content in Markdown
            title: Document title
            output_path: Optional file path to save PDF (if None, returns bytes)
            language: Language code for the document (default: "en")

        Returns:
            PDF bytes (if output_path is None) or writes to file

        Raises:
            TemplateNotFound: If template doesn't exist
            IOError: If writing to file fails
        """
        # Step 1: Sanitize and render Markdown to HTML
        sanitized_md = MarkdownRenderer.sanitize_markdown(markdown_content)
        html_content = MarkdownRenderer.render(sanitized_md)

        # Step 2: Load Jinja2 template from document_type subdirectory
        template_path = f"{self.document_type}/{self.template_name}.html"
        try:
            template = self.jinja_env.get_template(template_path)
        except TemplateNotFound:
            raise TemplateNotFound(
                f"Template '{template_path}' not found in {self.TEMPLATES_DIR}"
            )

        # Step 3: Render final HTML with template
        context = {
            "document_type": self.document_type,
            "title": title,
            "content": html_content,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "include_metadata": self.include_metadata,
            "font_size": self.font_size,
            "language": language,
        }
        final_html = template.render(**context)

        # Step 4: Load CSS (document_type specific)
        stylesheets = []

        # Base CSS for this document type
        base_css_path = self.CSS_DIR / self.document_type / "base.css"
        if base_css_path.exists():
            stylesheets.append(CSS(filename=str(base_css_path)))

        # Template-specific CSS
        template_css_path = self.CSS_DIR / self.document_type / f"{self.template_name}.css"
        if template_css_path.exists():
            stylesheets.append(CSS(filename=str(template_css_path)))

        # Step 5: Generate PDF with weasyprint
        html_obj = HTML(string=final_html, base_url=str(self.TEMPLATES_DIR))

        if output_path:
            # Write to file
            html_obj.write_pdf(
                target=str(output_path),
                stylesheets=stylesheets
            )
            return None
        else:
            # Return bytes
            pdf_bytes = html_obj.write_pdf(stylesheets=stylesheets)
            return pdf_bytes

    @staticmethod
    def get_available_document_types() -> list[str]:
        """
        Get all available document types.

        Returns:
            List of document type names (subdirectories in templates/)
        """
        templates_dir = PDFGenerator.TEMPLATES_DIR
        if not templates_dir.exists():
            return []

        # Get all subdirectories, excluding those starting with _
        document_types = [
            d.name for d in templates_dir.iterdir()
            if d.is_dir() and not d.name.startswith('_')
        ]

        return sorted(document_types)

    @staticmethod
    def get_available_templates(document_type: str) -> list[str]:
        """
        Get list of available templates for a specific document type.

        Args:
            document_type: Type of document (resume, cover_letter, etc.)

        Returns:
            List of template names (without .html extension)
        """
        template_dir = PDFGenerator.TEMPLATES_DIR / document_type
        if not template_dir.exists():
            return []

        # Find all .html files and extract template names
        template_files = template_dir.glob("*.html")
        templates = [f.stem for f in template_files if f.stem != "base"]

        return sorted(templates)

    @staticmethod
    def validate_template(document_type: str, template_name: str) -> bool:
        """
        Check if template exists for given document type.

        Args:
            document_type: Type of document
            template_name: Template name to validate

        Returns:
            True if template exists, False otherwise
        """
        return template_name in PDFGenerator.get_available_templates(document_type)
