import json
import uuid
from typing import Dict, List, Optional
from fastapi import UploadFile, HTTPException, status
from app.core.s3_client import upload_file, delete_file, get_file
from app.models.campaign import Campaign
from sqlalchemy.orm import Session


def generate_file_key(campaign_id: str, piece_type: str, commercial_space: Optional[str] = None, file_extension: str = "") -> str:
    file_id = str(uuid.uuid4())
    if commercial_space:
        safe_space = commercial_space.replace(" ", "_").replace("/", "_")
        return f"campaigns/{campaign_id}/{piece_type}/{safe_space}/{file_id}{file_extension}"
    else:
        return f"campaigns/{campaign_id}/{piece_type}/{file_id}{file_extension}"


async def upload_app_file(
    campaign: Campaign,
    commercial_space: str,
    file: UploadFile,
    db: Session
) -> str:

    if not file.filename.endswith('.png'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App files must be PNG format"
        )
    
    if commercial_space not in (campaign.commercial_spaces or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Commercial space '{commercial_space}' is not configured for this campaign"
        )
    
    file_content = await file.read()
    file_key = generate_file_key(campaign.id, "App", commercial_space, ".png")
    file_url = upload_file(file_content, file_key, "image/png")
    
    return file_url


async def upload_email_file(
    campaign: Campaign,
    file: UploadFile,
    db: Session
) -> str:
   
    if not file.filename.endswith('.html'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail files must be HTML format (.html extension)"
        )
    
    file_content = await file.read()
   
    try:
        content_str = file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content_str = file_content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo HTML inválido: não é possível decodificar o conteúdo. Certifique-se de que o arquivo é um HTML válido, não RTF ou outro formato."
            )
    
    if content_str.strip().startswith('{\\rtf1'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo parece ser RTF, não HTML. No TextEdit (macOS), certifique-se de salvar como 'Texto Simples' ou 'HTML' e não como 'RTF'. Ou use um editor de código como VS Code."
        )
    
    content_lower = content_str.strip().lower()
    if not (content_str.strip().startswith('<') or 
            '<html' in content_lower or 
            '<!doctype' in content_lower or
            '<body' in content_lower or
            '<div' in content_lower or
            '<p' in content_lower):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo não parece ser HTML válido. Certifique-se de que o arquivo contém tags HTML (como <html>, <body>, <div>, etc.)"
        )
    
    file_key = generate_file_key(campaign.id, "E-mail", None, ".html")
    file_url = upload_file(file_content, file_key, "text/html")
    
    return file_url


def update_app_file_urls(
    current_file_urls: Optional[str],
    commercial_space: str,
    new_file_url: str
) -> str:
    if current_file_urls:
        try:
            file_urls_dict = json.loads(current_file_urls)
        except json.JSONDecodeError:
            file_urls_dict = {}
    else:
        file_urls_dict = {}
    
    file_urls_dict[commercial_space] = new_file_url
    
    return json.dumps(file_urls_dict)


def get_app_file_urls_dict(file_urls: Optional[str]) -> Dict[str, str]:

    if not file_urls:
        return {}
    
    try:
        return json.loads(file_urls)
    except json.JSONDecodeError:
        return {}


def extract_file_key_from_url(file_url: str, bucket_name: str) -> Optional[str]:

    if not file_url or "/" not in file_url:
        return None
    
    try:
        parts = file_url.split("/")
        bucket_index = -1

        for i, part in enumerate(parts):
            if part == bucket_name:
                bucket_index = i
                break
        
        if bucket_index >= 0 and bucket_index + 1 < len(parts):
            file_key = "/".join(parts[bucket_index + 1:])
            return file_key
    except Exception:
        pass
    
    return None


def download_file_from_url(file_url: str, bucket_name: str) -> tuple[bytes, str]:
    """Download file from S3 using the file URL. Returns (content, content_type)."""
    file_key = extract_file_key_from_url(file_url, bucket_name)
    if not file_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file URL"
        )
    
    try:
        content, content_type = get_file(file_key)
        return content, content_type
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )

