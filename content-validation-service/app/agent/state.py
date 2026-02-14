from typing import TypedDict, Optional, Any


class ValidationGraphState(TypedDict, total=False):
    task: Optional[str]
    channel: Optional[str]
    content: Optional[dict]
    validation_result: Optional[dict]
    validation_valid: bool
    retrieve_ok: bool
    retrieve_error: Optional[str]
    content_for_compliance: Optional[dict]
    html_for_branding: Optional[str]    
    image_for_branding: Optional[str]   
    conversion_metadata: Optional[dict]
    retrieved_content_hash: Optional[str]
    specs_ok: Optional[bool]       
    specs_result: Optional[dict]
    compliance_ok: bool
    compliance_result: Optional[dict]
    compliance_error: Optional[str]
    branding_ok: Optional[bool] 
    branding_result: Optional[dict]
    branding_error: Optional[str]
    requires_human_approval: bool
    human_approval_reason: Optional[str]
    final_verdict: Optional[dict]
    orchestration_result: Optional[dict]
