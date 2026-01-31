import logging
import os
import re
from typing import List, Optional
from langchain_experimental.text_splitter import SemanticChunker as LangChainSemanticChunker
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class SemanticChunker:
    """Quebra o arquivo por semântica com embeddings."""

    def __init__(
        self,
        min_chunk_size: int = 100,
        max_chunk_size: int = 800,
        chunk_overlap: Optional[int] = None,
        embedding_provider: Optional[str] = None,
        embedding_model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        breakpoint_threshold_type: str = "percentile",
        breakpoint_threshold_amount: float = 75.0,  
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else max(100, int(max_chunk_size * 0.15))
        
        # canal no nome dos arquivos
        self.channel_patterns = {
            r'[_-]SMS[_-]': 'SMS',
            r'[_-]EMAIL[_-]': 'EMAIL',
            r'[_-]E-MAIL[_-]': 'EMAIL',
            r'[_-]PUSH[_-]': 'PUSH',
            r'[_-]APP[_-]': 'APP',
            r'[_-]BANNER[_-]': 'APP',
        }

        embedding_provider = embedding_provider or os.getenv("EMBEDDING_PROVIDER", "openai")
        embedding_model = embedding_model or os.getenv("EMBEDDING_MODEL")
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        env_base_url = os.getenv("OPENAI_BASE_URL", "")
        if env_base_url:
            env_base_url = env_base_url.strip()
        
        final_base_url = base_url if base_url else (env_base_url if env_base_url else None)
        if final_base_url:
            final_base_url = final_base_url.strip()
            if not final_base_url:
                final_base_url = None

        embeddings_kwargs = {}
        if api_key:
            embeddings_kwargs["openai_api_key"] = api_key
        if final_base_url:
            embeddings_kwargs["base_url"] = final_base_url
        if embedding_model:
            embeddings_kwargs["model"] = embedding_model
        try:
            t = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT", "60"))
            embeddings_kwargs["request_timeout"] = max(5.0, t)
        except (TypeError, ValueError):
            embeddings_kwargs["request_timeout"] = 60.0

        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)
        self.splitter = LangChainSemanticChunker(
            embeddings=self.embeddings,
            breakpoint_threshold_type=breakpoint_threshold_type,
            breakpoint_threshold_amount=breakpoint_threshold_amount,
            add_start_index=True,
        )

    def _extract_channel(self, file_name: str) -> str:
        file_name_upper = file_name.upper()
        
        for pattern, channel in self.channel_patterns.items():
            if re.search(pattern, file_name_upper):
                return channel
        
        return "GENERAL"

    def _ensure_chunk_starts_at_section(self, chunks: List[dict], original_text: str) -> List[dict]:
        """Ajusta chunks para começarem em seções numeradas quando próximo."""
        fixed_chunks = []
        
        for chunk in chunks:
            chunk_text = chunk["text"]
            start_char = chunk.get("start_char", 0)
            end_char = chunk.get("end_char", start_char + len(chunk_text))
            
            starts_with_section = re.match(r'^\s*\d+\.\s+[A-ZÀ-Ú]', chunk_text.strip())
            if not starts_with_section:
                # procura seção numerada próxima 
                search_start = max(0, start_char - 200)
                search_text = original_text[search_start:start_char]
                section_pattern = r'(\d+)\.\s+[A-ZÀ-Ú]'
                matches = list(re.finditer(section_pattern, search_text))
                
                if matches:
                    last_match = matches[-1]
                    match_pos = search_start + last_match.start()
                    
                    if (start_char - match_pos) < 100:
                        new_start = match_pos
                        new_text = original_text[new_start:end_char].strip()
                        
                        if len(new_text) >= self.min_chunk_size and len(new_text) <= self.max_chunk_size:
                            new_chunk = {
                                "text": new_text,
                                "start_char": new_start,
                                "end_char": end_char,
                                "char_count": len(new_text),
                            }
                            if "channel" in chunk:
                                new_chunk["channel"] = chunk["channel"]
                            fixed_chunks.append(new_chunk)
                            continue
            
            fixed_chunks.append(chunk)
        
        return fixed_chunks

    def _split_large_chunk(self, text: str) -> List[dict]:
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        start_pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            test_chunk = current_chunk + "\n\n" + para if current_chunk else para

            if len(test_chunk) <= self.max_chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    chunks.append({
                        "text": current_chunk,
                        "start_char": start_pos,
                        "end_char": start_pos + len(current_chunk),
                        "char_count": len(current_chunk),
                    })
                    start_pos += len(current_chunk) + 2
                current_chunk = para

        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append({
                "text": current_chunk,
                "start_char": start_pos,
                "end_char": start_pos + len(current_chunk),
                "char_count": len(current_chunk),
            })

        return chunks if chunks else [{
            "text": text[:self.max_chunk_size],
            "start_char": 0,
            "end_char": min(self.max_chunk_size, len(text)),
            "char_count": min(self.max_chunk_size, len(text)),
        }]

    def chunk(self, text: str, file_name: Optional[str] = None) -> List[dict]:
        if not text or not text.strip():
            return []

        channel = self._extract_channel(file_name) if file_name else "GENERAL"

        try:
            logger.info(
                "Computing semantic breakpoints (embedding sentences). "
                "This may take a while for long documents."
            )
            documents = self.splitter.create_documents([text])
            
            result = []
            for doc in documents:
                chunk_text = doc.page_content.strip()
                
                if len(chunk_text) < self.min_chunk_size:
                    continue
                
                if len(chunk_text) > self.max_chunk_size:
                    sub_chunks = self._split_large_chunk(chunk_text)
                    for chunk in sub_chunks:
                        chunk["channel"] = channel
                    result.extend(sub_chunks)
                else:
                    start_index = doc.metadata.get("start_index", 0)
                    result.append({
                        "text": chunk_text,
                        "start_char": start_index,
                        "end_char": start_index + len(chunk_text),
                        "char_count": len(chunk_text),
                        "channel": channel,
                    })
            
            result = self._ensure_chunk_starts_at_section(result, text)
            
            for chunk in result:
                if "channel" not in chunk:
                    chunk["channel"] = channel
            
            logger.info(
                f"Created {len(result)} semantic chunks (channel: {channel})."
            )
            return result

        except Exception as e:
            logger.error(f"Error in semantic chunking: {e}", exc_info=True)
            raise


def chunk_text(text: str, **kwargs) -> List[dict]:
    chunker = SemanticChunker(**kwargs)
    return chunker.chunk(text)
