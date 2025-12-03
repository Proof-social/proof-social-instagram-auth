# Implementação OAuth Instagram - Proof Social API

## 🎯 Objetivo Alcançado

Implementados com sucesso os 2 endpoints OAuth Instagram/Meta solicitados para completar o fluxo de autenticação com Firebase Auth:

1. **POST /auth/instagram/login** - Gera URL de autorização Meta/Instagram
2. **POST /auth/instagram/process-callback** - Processa callback OAuth e configura integração

## ✅ Implementações Realizadas

### 1. Schemas de Dados (`schemas/instagram.py`)

```python
class InstagramLoginRequest(BaseModel):
    redirect_uri: str

class InstagramLoginResponse(BaseModel):
    auth_url: str

class InstagramCallbackRequest(BaseModel):
    code: str
    state: str

class InstagramCallbackResponse(BaseModel):
    api_key: str
    instagram_accounts: List[InstagramAccount]
    pages: List[InstagramPage]
    message: str
```

### 2. Validação Firebase Auth (`core/security.py`)

```python
async def verify_firebase_token(authorization: str) -> str:
    """Valida token Firebase Auth e retorna user_uid"""
```

**Características:**

- Validação real de tokens Firebase usando Firebase Admin SDK
- Extração segura do `user_uid` do token
- Tratamento robusto de erros
- Logs detalhados para auditoria

### 3. Endpoints OAuth Instagram (`routes/auth.py`)

#### POST /auth/instagram/login

- **Input:** `Authorization: Bearer {firebase_token}` + `{ redirect_uri }`
- **Output:** `{ auth_url }`
- **Funcionalidade:**
  - Valida token Firebase
  - Busca configurações Meta do Secret Manager
  - Gera URL de autorização com state=user_uid
  - Inclui todas as permissões Instagram necessárias:
    - `pages_show_list`
    - `ads_management`
    - `ads_read`
    - `instagram_basic`
    - `instagram_manage_comments`
    - `instagram_manage_insights`
    - `instagram_content_publish`
    - `instagram_manage_messages`
    - `pages_read_engagement`
    - `pages_manage_ads`
    - `instagram_branded_content_ads_brand`
    - `instagram_manage_events`

#### POST /auth/instagram/process-callback

- **Input:** `Authorization: Bearer {firebase_token}` + `{ code, state }`
- **Output:** `{ api_key, instagram_accounts, pages, message }`
- **Funcionalidade:**
  - Valida token Firebase e state
  - Troca `code` por `access_token` via API Meta
  - Converte para token de longa duração
  - Salva token no Secret Manager
  - Gera API key única (UUID)
  - Salva integração no Firestore
  - Busca contas Instagram e páginas conectadas
  - Retorna dados completos da integração

### 4. Integração Multi-Tenant

Os endpoints seguem a arquitetura multi-tenant existente:

- **Isolamento:** Cada usuário tem suas próprias credenciais
- **Segurança:** Tokens salvos no Secret Manager com prefixo `proof-social-instagram-{user_uid}`
- **Performance:** API keys indexadas para busca O(1)
- **Consistência:** Usa o mesmo padrão dos outros endpoints

## 🔧 Como Usar

### 1. Iniciar Fluxo OAuth

```bash
curl -X POST "https://your-api-url/auth/instagram/login" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "https://your-app.com/auth/instagram/callback"}'
```

**Resposta:**

```json
{
  "auth_url": "https://www.facebook.com/v20.0/dialog/oauth?client_id=...&redirect_uri=...&state=user_uid&response_type=code&scope=pages_show_list,ads_management,ads_read,instagram_basic,instagram_manage_comments,instagram_manage_insights,instagram_content_publish,instagram_manage_messages,pages_read_engagement,pages_manage_ads,instagram_branded_content_ads_brand,instagram_manage_events"
}
```

### 2. Processar Callback

```bash
curl -X POST "https://your-api-url/auth/instagram/process-callback" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "AUTHORIZATION_CODE", "state": "USER_UID"}'
```

**Resposta:**

```json
{
  "api_key": "123e4567-e89b-12d3-a456-426614174000",
  "instagram_accounts": [
    {
      "id": "17841405309211844",
      "username": "your_instagram_account",
      "name": "Your Instagram Account"
    }
  ],
  "pages": [
    {
      "id": "123456789",
      "name": "Your Facebook Page",
      "instagram_business_account": {
        "id": "17841405309211844",
        "username": "your_instagram_account",
        "name": "Your Instagram Account"
      }
    }
  ],
  "message": "Integração Instagram configurada com sucesso"
}
```

## 🔄 Fluxo Completo

1. **Frontend** chama `/auth/instagram/login` com token Firebase
2. **Backend** gera URL de autorização Meta/Instagram
3. **Usuário** é redirecionado para Meta para autorizar
4. **Meta** redireciona para `redirect_uri` com `code` e `state`
5. **Frontend** chama `/auth/instagram/process-callback` com `code` e `state`
6. **Backend** processa, salva credenciais e retorna `api_key`
7. **Frontend** pode usar `api_key` para chamadas à API

## 🔐 Segurança

- ✅ **Autenticação Firebase:** Todos os endpoints requerem token Firebase válido
- ✅ **Validação de State:** Verifica se `state` corresponde ao `user_uid`
- ✅ **Secret Manager:** Tokens salvos de forma segura
- ✅ **API Keys Únicas:** Geradas automaticamente para cada usuário
- ✅ **Isolamento:** Cada usuário tem suas próprias credenciais
- ✅ **Logs:** Auditoria completa de todas as operações

## 📁 Arquivos Criados

- ✅ `main.py` - Aplicação FastAPI principal
- ✅ `requirements.txt` - Dependências Python
- ✅ `schemas/instagram.py` - Schemas OAuth Instagram
- ✅ `core/security.py` - Validação Firebase e Secret Manager
- ✅ `routes/auth.py` - Endpoints OAuth Instagram
- ✅ `examples/instagram_oauth_usage_example.py` - Exemplo de uso
- ✅ `README.md` - Documentação principal
- ✅ `INSTAGRAM_OAUTH_IMPLEMENTATION.md` - Esta documentação

## 🚀 Status

**✅ IMPLEMENTAÇÃO COMPLETA**

Os endpoints OAuth Instagram foram implementados com sucesso e estão prontos para uso. A implementação segue todas as boas práticas de segurança e integração com a arquitetura multi-tenant existente.

## 📝 Permissões Instagram Implementadas

A aplicação solicita e gerencia as seguintes permissões do Instagram/Meta:

1. **pages_show_list** - Listar páginas do Facebook conectadas
2. **ads_management** - Gerenciar anúncios
3. **ads_read** - Ler dados de anúncios
4. **instagram_basic** - Acesso básico ao Instagram
5. **instagram_manage_comments** - Gerenciar comentários
6. **instagram_manage_insights** - Gerenciar insights e métricas
7. **instagram_content_publish** - Publicar conteúdo
8. **instagram_manage_messages** - Gerenciar mensagens diretas
9. **pages_read_engagement** - Ler engajamento das páginas
10. **pages_manage_ads** - Gerenciar anúncios das páginas
11. **instagram_branded_content_ads_brand** - Gerenciar conteúdo patrocinado
12. **instagram_manage_events** - Gerenciar eventos

Todas essas permissões são incluídas automaticamente na URL de autorização OAuth.

