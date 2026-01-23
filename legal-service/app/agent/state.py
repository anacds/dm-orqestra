from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    """State do agente jurídico"""
    
    # Input estruturado
    task: Optional[str]
    channel: Optional[str]
    content: Optional[str]  # Mantido para backward compatibility
    content_title: Optional[str]  # Para PUSH
    content_body: Optional[str]  # Para SMS e PUSH
    
    # Resultados da busca
    retrieved_chunks: List[dict]
    search_metadata: Optional[dict]
    
    # Contexto para geração
    context: str
    sources: List[str]
    
    # Output estruturado
    decision: Optional[str]
    severity: Optional[str]
    requires_human_review: Optional[bool]
    summary: Optional[str]
    
    # Metadados
    iteration_count: int
    max_iterations: int

