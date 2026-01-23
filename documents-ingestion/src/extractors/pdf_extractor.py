import logging
import re
from pathlib import Path
from typing import Optional

import fitz

logger = logging.getLogger(__name__)


class PDFExtractor:
    def extract(self, file_path: Path) -> dict:
        try:
            doc = fitz.open(file_path)
            pages = []
            metadata = doc.metadata or {}

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                pages.append(text)

            full_text = "\n\n".join(pages)

            # Extrai título do PDF, ou infere do nome do arquivo se vazio
            title = metadata.get("title", "").strip()
            if not title:
                # Remove extensão e normaliza o nome do arquivo
                title = file_path.stem
                # Remove padrões comuns como "_v1", "-v1", etc.
                title = re.sub(r'[_\s]*-?[vV]\d+[\.\d]*$', '', title)
                title = re.sub(r'[_\s-]+', ' ', title).strip()

            # Filtra campos vazios e mantém apenas os que têm valor
            clean_metadata = {
                "source_file": str(file_path),
                "file_name": file_path.name,
                "page_count": len(doc),
            }

            if title:
                clean_metadata["title"] = title
            
            author = metadata.get("author", "").strip()
            if author:
                clean_metadata["author"] = author
            
            subject = metadata.get("subject", "").strip()
            if subject:
                clean_metadata["subject"] = subject
            
            creator = metadata.get("creator", "").strip()
            if creator:
                clean_metadata["creator"] = creator
            
            producer = metadata.get("producer", "").strip()
            if producer:
                clean_metadata["producer"] = producer
            
            creation_date = metadata.get("creationDate", "").strip()
            if creation_date:
                clean_metadata["creation_date"] = creation_date
            
            modification_date = metadata.get("modDate", "").strip()
            if modification_date:
                clean_metadata["modification_date"] = modification_date

            result = {
                "text": full_text,
                "metadata": clean_metadata,
                "page_count": len(doc),
            }

            doc.close()

            logger.info(
                f"Extracted {len(pages)} pages from {file_path.name} "
                f"({len(full_text)} characters)"
            )

            return result

        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
            raise


def extract_pdf(file_path: Path) -> dict:
    extractor = PDFExtractor()
    return extractor.extract(file_path)

