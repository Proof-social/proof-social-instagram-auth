"""
Schemas para autenticação OAuth Instagram/Meta
"""

from pydantic import BaseModel
from typing import List, Optional


class InstagramLoginRequest(BaseModel):
    """Request para iniciar fluxo OAuth"""
    redirect_uri: str
    # Quando True, frontend quer FORÇAR escolha de conta nova (usuário já
    # tem uma conta conectada e quer adicionar outra). Backend prefixa o
    # OAuth URL com logout do IG pra não auto-continuar a sessão atual.
    force_new_account: bool = False


class InstagramLoginResponse(BaseModel):
    """Response com URL de autorização"""
    auth_url: str


class InstagramCallbackRequest(BaseModel):
    """Request para processar callback OAuth"""
    code: str
    state: str
    redirect_uri: str


class InstagramAccount(BaseModel):
    """Conta do Instagram"""
    id: str
    username: Optional[str] = None
    name: Optional[str] = None


class InstagramPage(BaseModel):
    """Página do Facebook conectada ao Instagram"""
    id: str
    name: str
    instagram_business_account: Optional[InstagramAccount] = None


class InstagramCallbackResponse(BaseModel):
    """Response após processar callback"""
    api_key: str
    instagram_accounts: List[InstagramAccount]
    message: str
    status: str
    redirect_url: Optional[str] = None

