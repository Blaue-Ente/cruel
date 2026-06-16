import PyPDF2
from io import BytesIO
import re
import logging
from typing import List, Optional
from app.scraperio.models import KnowledgebaseItem
from .base import BaseExtractor


class PDFExtractor(BaseExtractor):
    """Extract content from PDF files"""
    
    def extract_from_file(self, file_path: str, author: str = "", max_pages: int = None) -> List[KnowledgebaseItem]:
        """Extract content from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                return self._extract_pdf_content(file, author, max_pages)
        except Exception as e:
            logging.error(f"Error extracting PDF {file_path}: {e}")
            return []
    
    def extract_from_bytes(self, pdf_bytes: bytes, author: str = "", max_pages: int = None) -> List[KnowledgebaseItem]:
        """Extract content from PDF bytes"""
        try:
            file_obj = BytesIO(pdf_bytes)
            return self._extract_pdf_content(file_obj, author, max_pages)
        except Exception as e:
            logging.error(f"Error extracting PDF from bytes: {e}")
            return []
    
    def _extract_pdf_content(self, file_obj, author: str, max_pages: int = None) -> List[KnowledgebaseItem]:
        """Extract content from PDF file object"""
        reader = PyPDF2.PdfReader(file_obj)
        items = []
        
        # Extract text from each page
        pages_to_process = min(len(reader.pages), max_pages or len(reader.pages))
        
        current_chapter = ""
        current_content = ""
        chapter_count = 0
        
        for i in range(pages_to_process):
            page = reader.pages[i]
            text = page.extract_text()
            
            # Try to detect chapter boundaries
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                
                # Check if this looks like a chapter heading
                if self._is_chapter_heading(line):
                    # Save previous chapter if it exists
                    if current_chapter and current_content:
                        items.append(KnowledgebaseItem(
                            title=current_chapter,
                            content=current_content.strip(),
                            content_type="book",
                            author=author
                        ))
                        chapter_count += 1
                    
                    # Start new chapter
                    current_chapter = line
                    current_content = ""
                else:
                    current_content += line + "\n"
        
        # Add the last chapter
        if current_chapter and current_content:
            items.append(KnowledgebaseItem(
                title=current_chapter,
                content=current_content.strip(),
                content_type="book",
                author=author
            ))
        
        # If no chapters detected, create one item with all content
        if not items and pages_to_process > 0:
            all_text = ""
            for i in range(pages_to_process):
                all_text += reader.pages[i].extract_text() + "\n"
            
            items.append(KnowledgebaseItem(
                title="PDF Content",
                content=all_text.strip(),
                content_type="book",
                author=author
            ))
        
        return items
    
    def _is_chapter_heading(self, line: str) -> bool:
        """Check if a line looks like a chapter heading"""
        line = line.strip()
        
        # Common chapter patterns
        patterns = [
            r'^Chapter \d+',
            r'^\d+\.\s',
            r'^CHAPTER \d+',
            r'^Part \d+',
            r'^Section \d+'
        ]
        
        for pattern in patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Check if it's a short line that might be a heading
        return len(line) < 100 and len(line) > 5 and line.isupper() 