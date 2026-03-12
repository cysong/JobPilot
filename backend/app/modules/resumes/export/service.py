"""
Universal document export service.
Supports resume, cover_letter, and other document types.
"""
from typing import Optional
from pathlib import Path
import re

from .generator import PDFGenerator


class DocumentExportService:
    """
    Universal document export service.

    Provides a unified interface for exporting different document types
    (resume, cover_letter, etc.) to PDF format.
    """

    @staticmethod
    def export_to_pdf(
        document_type: str,
        content: str,
        title: str,
        template: Optional[str] = None,
        font_size: int = 12,
        include_metadata: bool = False,
        output_path: Optional[Path] = None
    ) -> tuple[bytes, str, str]:
        """
        Export document to PDF.

        Args:
            document_type: Type of document (resume, cover_letter, etc.)
            content: Document content in Markdown format
            title: Document title
            template: Template name (modern/classic/minimal), uses default if not specified
            font_size: Base font size in pt (10-16)
            include_metadata: Include generation timestamp in footer
            output_path: Optional file path to save PDF

        Returns:
            Tuple of (pdf_bytes, filename, template_used)

        Raises:
            ValueError: If document_type or template is invalid
            Exception: If PDF generation fails
        """
        # Initialize generator
        generator = PDFGenerator(
            document_type=document_type,
            template_name=template,
            font_size=font_size,
            include_metadata=include_metadata
        )

        # Generate PDF
        pdf_bytes = generator.generate(
            markdown_content=content,
            title=title,
            output_path=output_path
        )

        # Generate safe filename
        safe_title = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", title.strip())).strip("_") or "document"
        safe_type = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", document_type.strip())).strip("_") or "document"
        filename = f"{safe_title}_{safe_type}.pdf"

        return pdf_bytes, filename, generator.template_name

    @staticmethod
    def get_available_document_types() -> list[str]:
        """
        Get all available document types.

        Returns:
            List of document type names
        """
        return PDFGenerator.get_available_document_types()

    @staticmethod
    def get_available_templates(document_type: str) -> list[str]:
        """
        Get available templates for a specific document type.

        Args:
            document_type: Type of document

        Returns:
            List of template names
        """
        return PDFGenerator.get_available_templates(document_type)

    @staticmethod
    def validate_template(document_type: str, template_name: str) -> bool:
        """
        Validate if template exists for document type.

        Args:
            document_type: Type of document
            template_name: Template name to validate

        Returns:
            True if valid, False otherwise
        """
        return PDFGenerator.validate_template(document_type, template_name)
