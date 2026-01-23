import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SectionChunker:
    """Quebra o arquivo por seção, levando em conta títulos enumerados."""

    def __init__(self, min_chunk_size: int = 100):
        self.min_chunk_size = min_chunk_size
        # título de seção
        self.section_pattern = re.compile(r'^(\d+)\.\s+([^\n]+)', re.MULTILINE)
        # canal no nome dos arquivos
        self.channel_patterns = {
            r'[_-]SMS[_-]': 'SMS',
            r'[_-]EMAIL[_-]': 'EMAIL',
            r'[_-]E-MAIL[_-]': 'EMAIL',
            r'[_-]PUSH[_-]': 'PUSH',
            r'[_-]APP[_-]': 'APP',
            r'[_-]BANNER[_-]': 'APP',
        }
    
    def _extract_channel(self, file_name: str) -> str:
        file_name_upper = file_name.upper()
        
        for pattern, channel in self.channel_patterns.items():
            if re.search(pattern, file_name_upper):
                return channel
        
        return "GENERAL"
    
    def chunk(self, text: str, file_name: str, page_count: Optional[int] = None) -> List[Dict]:
        """Divide o texto por seções numeradas."""
        
        channel = self._extract_channel(file_name)
        sections = []
        matches = list(self.section_pattern.finditer(text))
        
        if not matches:
            if len(text) >= self.min_chunk_size:
                return [{
                    "text": text,
                    "start_char": 0,
                    "end_char": len(text),
                    "char_count": len(text),
                    "channel": channel,
                    "section_name": "Documento",
                    "section_number": None
                }]
            return []
        
        for i, match in enumerate(matches):
            section_number = match.group(1)
            section_name = match.group(2).strip()
            section_start = match.start()
            
            if i + 1 < len(matches):
                section_end = matches[i + 1].start()
            else:
                section_end = len(text)
            
            section_text = text[section_start:section_end].strip()
            
            if len(section_text) < self.min_chunk_size:
                continue
                        
            sections.append({
                "text": section_text,
                "start_char": section_start,
                "end_char": section_end,
                "char_count": len(section_text),
                "channel": channel,
                "section_name": section_name,
                "section_number": int(section_number)
            })
        
        logger.info(
            f"Created {len(sections)} section-based chunks from {file_name} "
            f"(channel: {channel})"
        )
        
        return sections


def chunk_by_sections(text: str, file_name: str, **kwargs) -> List[Dict]:
    chunker = SectionChunker(**kwargs)
    return chunker.chunk(text, file_name)

