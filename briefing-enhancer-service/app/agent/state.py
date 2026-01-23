from typing import TypedDict, Optional, List, Dict

class FieldEnhancement(TypedDict, total=False):
    """Represents a single field enhancement result."""
    field_name: str
    original_text: str
    enhanced_text: str
    explanation: str
    timestamp: str 

class EnhancementGraphState(TypedDict, total=False):
    """State structure for the enhancement LangGraph workflow."""
    field_name: str
    text: str
    field_info: Optional[dict]
    enhanced_text: Optional[str]
    explanation: Optional[str]
    enhancement_history: Optional[List[FieldEnhancement]]
    previous_fields_summary: Optional[str]
    campaign_name: Optional[str]

