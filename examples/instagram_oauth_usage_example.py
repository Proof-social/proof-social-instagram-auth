"""
Exemplo de uso da API de autenticação OAuth Instagram
"""

import httpx
import asyncio


# Configurações
API_BASE_URL = "https://your-api-url"
FIREBASE_TOKEN = "YOUR_FIREBASE_TOKEN"
REDIRECT_URI = "https://your-app.com/auth/instagram/callback"


async def example_instagram_oauth_flow():
    """Exemplo completo do fluxo OAuth Instagram"""
    
    async with httpx.AsyncClient() as client:
        # 1. Iniciar fluxo OAuth
        print("1. Iniciando fluxo OAuth...")
        login_response = await client.post(
            f"{API_BASE_URL}/auth/instagram/login",
            headers={
                "Authorization": f"Bearer {FIREBASE_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "redirect_uri": REDIRECT_URI
            }
        )
        
        if login_response.status_code != 200:
            print(f"Erro ao gerar URL de autorização: {login_response.text}")
            return
        
        login_data = login_response.json()
        auth_url = login_data["auth_url"]
        
        print(f"✅ URL de autorização gerada:")
        print(f"   {auth_url}")
        print(f"\n2. Redirecione o usuário para esta URL")
        print(f"3. Após autorização, Meta redirecionará para:")
        print(f"   {REDIRECT_URI}?code=AUTHORIZATION_CODE&state=USER_UID")
        
        # 4. Processar callback (simulação)
        print("\n4. Processando callback...")
        callback_response = await client.post(
            f"{API_BASE_URL}/auth/instagram/process-callback",
            headers={
                "Authorization": f"Bearer {FIREBASE_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "code": "AUTHORIZATION_CODE_FROM_META",
                "state": "USER_UID_FROM_STATE"
            }
        )
        
        if callback_response.status_code != 200:
            print(f"Erro ao processar callback: {callback_response.text}")
            return
        
        callback_data = callback_response.json()
        
        print(f"✅ Integração configurada com sucesso!")
        print(f"   API Key: {callback_data['api_key']}")
        print(f"   Contas Instagram: {len(callback_data['instagram_accounts'])}")
        print(f"   Páginas: {len(callback_data['pages'])}")
        
        # Exibir contas Instagram
        for account in callback_data["instagram_accounts"]:
            print(f"\n   📱 Instagram: @{account.get('username', 'N/A')}")
            print(f"      ID: {account['id']}")
        
        # Exibir páginas
        for page in callback_data["pages"]:
            print(f"\n   📄 Página: {page['name']}")
            print(f"      ID: {page['id']}")
            if page.get("instagram_business_account"):
                ig = page["instagram_business_account"]
                print(f"      Instagram: @{ig.get('username', 'N/A')}")


if __name__ == "__main__":
    print("=" * 60)
    print("Exemplo de Uso - Proof Social Instagram OAuth API")
    print("=" * 60)
    print()
    
    print("⚠️  ATENÇÃO: Configure as variáveis no início do arquivo:")
    print("   - API_BASE_URL")
    print("   - FIREBASE_TOKEN")
    print("   - REDIRECT_URI")
    print()
    
    # Descomente para executar
    # asyncio.run(example_instagram_oauth_flow())

