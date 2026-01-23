import httpx
from typing import Optional, Dict
from app.core.config import settings


class AuthServiceClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.AUTH_SERVICE_URL
        self.timeout = 10.0
    
    async def get_user_by_id(self, user_id: str, token: str) -> Optional[Dict]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/auth/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception:
                return None

auth_client = AuthServiceClient()

