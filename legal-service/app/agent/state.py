from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    task: Optional[str]
    channel: Optional[str]
    content: Optional[str]  
    content_title: Optional[str]  
    content_body: Optional[str] 
    content_image: Optional[str] 
    retrieved_chunks: List[dict]
    search_metadata: Optional[dict]
    context: str
    sources: List[str]
    decision: Optional[str]
    requires_human_review: Optional[bool]
    summary: Optional[str]    
    iteration_count: int
    max_iterations: int

