from __future__ import annotations

from pathlib import Path
from typing import List
import PyPDF2
import logging

from backend.knowledge.loaders.base_loader import BaseDocumentLoader

logger = logging.getLogger("eggman")


class PDFLoader(BaseDocumentLoader):
    """Document loader for PDF files using PyPDF2."""

    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    def load(self, file_path: Path) -> str:
        logger.info("PDFLoader: loading file %s", file_path)
        text_content = []
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
                logger.info("PDFLoader: processing %d pages from %s", num_pages, file_path.name)
                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
            
            full_text = "\n".join(text_content).strip()
            logger.info("PDFLoader: successfully extracted %d characters from %s", len(full_text), file_path.name)
            return full_text
        except Exception as e:
            logger.error("PDFLoader: failed to extract text from %s: %s", file_path, e)
            raise e

    def load_pages(self, file_path: Path) -> List[tuple[int, str]]:
        """Return per-page text with page numbers."""
        pages: List[tuple[int, str]] = []
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for i in range(len(reader.pages)):
                    text = reader.pages[i].extract_text()
                    if text:
                        pages.append((i + 1, text))
            logger.info("PDFLoader: extracted %d pages from %s", len(pages), file_path.name)
            return pages
        except Exception as e:
            logger.error("PDFLoader: failed to extract pages from %s: %s", file_path, e)
            raise e
