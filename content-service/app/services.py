import httpx
import hashlib
import uuid
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.creative_piece_analysis import CreativePieceAnalysis


class CreativePieceAnalysisService:
    """Service for analyzing creative pieces against campaign briefing and guidelines"""
    
    @staticmethod
    def calculate_content_hash(channel: str, content: Dict[str, str]) -> str:
        """Calculate hash of piece content to detect changes"""
        if channel == "SMS":
            content_str = f"SMS:{content.get('text', '')}"
        elif channel == "Push":
            content_str = f"Push:{content.get('title', '')}:{content.get('body', '')}"
        else:
            raise ValueError(f"Invalid channel: {channel}")
        
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    
    @staticmethod
    def get_existing_analysis(
        db: Session,
        campaign_id: str,
        channel: str,
        content_hash: str
    ) -> Optional[CreativePieceAnalysis]:
        """Get existing analysis for a piece with matching content hash"""
        return db.query(CreativePieceAnalysis).filter(
            CreativePieceAnalysis.campaign_id == campaign_id,
            CreativePieceAnalysis.channel == channel,
            CreativePieceAnalysis.content_hash == content_hash
        ).first()
    
    @staticmethod
    async def analyze_piece(
        db: Session,
        campaign_id: str,
        channel: str,
        content: Dict[str, str],
        user_id: str,
        auth_token: str
    ) -> CreativePieceAnalysis:
        """
        Analyze a creative piece against campaign briefing and guidelines.
        
        If analysis already exists for the same content, returns existing analysis.
        Otherwise, creates a new analysis.
        
        Args:
            db: Database session
            campaign_id: Campaign ID
            channel: "SMS" or "Push"
            content: Dict with piece content (text for SMS, title+body for Push)
            user_id: ID of user requesting the analysis
            auth_token: JWT authorization token
            
        Returns:
            CreativePieceAnalysis object
        """
        # Calculate content hash
        content_hash = CreativePieceAnalysisService.calculate_content_hash(channel, content)
        
        # Check if analysis already exists
        existing = CreativePieceAnalysisService.get_existing_analysis(
            db, campaign_id, channel, content_hash
        )
        if existing:
            return existing
        
        # Fetch campaign data for analysis context
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{settings.CAMPAIGNS_SERVICE_URL}/api/campaigns/{campaign_id}",
                    headers={"Authorization": auth_token}
                )
                
                if response.status_code == 404:
                    raise Exception("Campaign not found")
                elif response.status_code != 200:
                    raise Exception(f"Failed to fetch campaign: {response.status_code}")
                
                campaign = response.json()
        except httpx.TimeoutException:
            raise Exception("Campaigns service timeout")
        except httpx.ConnectError:
            raise Exception("Campaigns service unavailable")
        except Exception as e:
            raise Exception(f"Error fetching campaign: {str(e)}")
        
        # Perform analysis (mock implementation)
        analysis_result = CreativePieceAnalysisService._perform_analysis(
            channel, content, campaign
        )
        
        # Create and save analysis
        analysis = CreativePieceAnalysis(
            id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            channel=channel,
            content_hash=content_hash,
            is_valid=analysis_result["is_valid"],
            analysis_text=analysis_result["analysis_text"],
            analyzed_by=user_id
        )
        
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        return analysis
    
    @staticmethod
    def _perform_analysis(channel: str, content: Dict[str, str], campaign: Dict) -> Dict[str, str]:
        """
        Perform validation analysis against briefing and guidelines.
        
        This is a mock implementation. In production, this would use AI/LLM
        to validate the piece against campaign briefing and company guidelines.
        
        Returns:
            Dict with "is_valid" ("valid" | "invalid" | "warning") and "analysis_text"
        """
        campaign_name = campaign.get("name", "Campanha")
        business_objective = campaign.get("businessObjective", "")
        communication_tone = campaign.get("communicationTone", "Informal")
        target_audience = campaign.get("targetAudienceDescription", "")
        
        issues = []
        
        if channel == "SMS":
            text = content.get("text", "")
            
            # Validate SMS length
            if len(text) > 160:
                issues.append(f"❌ SMS excede o limite de 160 caracteres ({len(text)} caracteres)")
            
            # Validate tone alignment (basic checks)
            if communication_tone == "Formal" and any(word in text.lower() for word in ["!", "🎯", "⚡"]):
                issues.append("⚠️ O tom formal foi solicitado, mas o texto contém elementos informais (emoji, exclamações)")
            
            # Validate content relevance (basic check)
            if business_objective and business_objective.lower() not in text.lower():
                issues.append("⚠️ O texto não parece relacionado diretamente ao objetivo de negócio da campanha")
            
            # Generate analysis text
            if not issues:
                analysis_text = f"✅ Validação aprovada!\n\nO texto SMS está de acordo com o briefing da campanha '{campaign_name}' e as diretrizes da empresa:\n- Tamanho adequado ({len(text)} caracteres)\n- Tom de comunicação apropriado ({communication_tone})\n- Conteúdo relevante ao objetivo de negócio"
                is_valid = "valid"
            elif len([i for i in issues if i.startswith("❌")]) > 0:
                analysis_text = f"❌ Validação reprovada!\n\nProblemas encontrados:\n" + "\n".join(issues)
                is_valid = "invalid"
            else:
                analysis_text = f"⚠️ Validação com ressalvas:\n\n" + "\n".join(issues)
                is_valid = "warning"
        
        elif channel == "Push":
            title = content.get("title", "")
            body = content.get("body", "")
            
            # Validate Push title length
            if len(title) > 50:
                issues.append(f"❌ Título excede o limite recomendado de 50 caracteres ({len(title)} caracteres)")
            
            # Validate Push body length
            if len(body) > 120:
                issues.append(f"⚠️ Corpo excede o limite recomendado de 120 caracteres ({len(body)} caracteres)")
            
            # Validate tone alignment
            if communication_tone == "Formal" and any(word in (title + body).lower() for word in ["!", "🎯", "⚡"]):
                issues.append("⚠️ O tom formal foi solicitado, mas o texto contém elementos informais (emoji, exclamações)")
            
            # Validate content relevance
            if business_objective and business_objective.lower() not in (title + body).lower():
                issues.append("⚠️ O conteúdo não parece relacionado diretamente ao objetivo de negócio da campanha")
            
            # Generate analysis text
            if not issues:
                analysis_text = f"✅ Validação aprovada!\n\nA notificação Push está de acordo com o briefing da campanha '{campaign_name}' e as diretrizes da empresa:\n- Título adequado ({len(title)} caracteres)\n- Corpo adequado ({len(body)} caracteres)\n- Tom de comunicação apropriado ({communication_tone})\n- Conteúdo relevante ao objetivo de negócio"
                is_valid = "valid"
            elif len([i for i in issues if i.startswith("❌")]) > 0:
                analysis_text = f"❌ Validação reprovada!\n\nProblemas encontrados:\n" + "\n".join(issues)
                is_valid = "invalid"
            else:
                analysis_text = f"⚠️ Validação com ressalvas:\n\n" + "\n".join(issues)
                is_valid = "warning"
        else:
            raise ValueError(f"Invalid channel: {channel}")
        
        return {
            "is_valid": is_valid,
            "analysis_text": analysis_text
        }
