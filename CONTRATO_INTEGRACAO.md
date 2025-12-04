# 📋 Contrato de Integração - Proof Social Instagram OAuth API

## 🌐 URL Base da API

```
https://proof-social-instagram-auth-30922479426.us-central1.run.app
```

## 🔐 Autenticação

Todos os endpoints OAuth requerem autenticação via **Firebase Auth Token** no header `Authorization`:

```
Authorization: Bearer {firebase_token}
```

---

## 📍 Endpoints

### 1. GET / - Informações do Serviço

**Descrição:** Retorna informações básicas sobre a API

**Método:** `GET`  
**Autenticação:** Não requerida

**Request:**
```http
GET / HTTP/1.1
Host: proof-social-instagram-auth-30922479426.us-central1.run.app
```

**Response 200:**
```json
{
  "message": "Proof Social Instagram Auth API",
  "version": "1.0.0",
  "status": "running"
}
```

---

### 2. GET /health - Health Check

**Descrição:** Verifica se o serviço está funcionando

**Método:** `GET`  
**Autenticação:** Não requerida

**Request:**
```http
GET /health HTTP/1.1
Host: proof-social-instagram-auth-30922479426.us-central1.run.app
```

**Response 200:**
```json
{
  "status": "healthy"
}
```

---

### 3. POST /auth/instagram/login - Iniciar Fluxo OAuth

**Descrição:** Gera URL de autorização Meta/Instagram para iniciar o fluxo OAuth

**Método:** `POST`  
**Autenticação:** ✅ Requerida (Firebase Token)  
**Path:** `/auth/instagram/login`

**Request Headers:**
```http
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "redirect_uri": "https://seu-dominio.com/auth/instagram/callback"
}
```

**Parâmetros:**
- `redirect_uri` (string, obrigatório): URL para onde o Meta redirecionará após autorização. Deve estar configurada nas "Valid OAuth Redirect URIs" do app Meta.

**Exemplo de Request:**
```bash
curl -X POST "https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/login" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
  }'
```

**Response 200:**
```json
{
  "auth_url": "https://www.facebook.com/v20.0/dialog/oauth?client_id=4109658012632973&redirect_uri=https://app.proof-social.com/auth/instagram/callback&state=user123&response_type=code&scope=pages_show_list,ads_management,ads_read,instagram_basic,instagram_manage_comments,instagram_manage_insights,instagram_content_publish,instagram_manage_messages,pages_read_engagement,pages_manage_ads,instagram_branded_content_ads_brand,instagram_manage_events"
}
```

**Response Fields:**
- `auth_url` (string): URL completa para redirecionar o usuário ao Meta para autorização

**Erros Possíveis:**

**401 Unauthorized:**
```json
{
  "detail": "Token de autorização não fornecido"
}
```
ou
```json
{
  "detail": "Token inválido: ..."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Erro ao gerar URL de autorização: ..."
}
```

---

### 4. POST /auth/instagram/process-callback - Processar Callback OAuth

**Descrição:** Processa o callback do Meta após autorização e configura a integração Instagram

**Método:** `POST`  
**Autenticação:** ✅ Requerida (Firebase Token)  
**Path:** `/auth/instagram/process-callback`

**Request Headers:**
```http
Authorization: Bearer {firebase_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "code": "AUTHORIZATION_CODE_FROM_META",
  "state": "USER_UID_FROM_STATE",
  "redirect_uri": "https://seu-dominio.com/auth/instagram/callback"
}
```

**Parâmetros:**
- `code` (string, obrigatório): Código de autorização retornado pelo Meta no callback
- `state` (string, obrigatório): State que foi enviado na URL de autorização (deve corresponder ao user_uid)
- `redirect_uri` (string, obrigatório): Mesma redirect_uri usada no login (deve ser exatamente igual)

**Exemplo de Request:**
```bash
curl -X POST "https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AQBx...",
    "state": "user123",
    "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
  }'
```

**Response 200:**
```json
{
  "api_key": "123e4567-e89b-12d3-a456-426614174000",
  "instagram_accounts": [
    {
      "id": "17841405309211844",
      "username": "minha_conta_instagram",
      "name": "Minha Conta Instagram"
    }
  ],
  "pages": [
    {
      "id": "123456789",
      "name": "Minha Página Facebook",
      "instagram_business_account": {
        "id": "17841405309211844",
        "username": "minha_conta_instagram",
        "name": "Minha Conta Instagram"
      }
    }
  ],
  "message": "Integração Instagram configurada com sucesso"
}
```

**Response Fields:**
- `api_key` (string, UUID): Chave única gerada para esta integração. Use esta chave para identificar a integração em chamadas futuras.
- `instagram_accounts` (array): Lista de contas Instagram Business conectadas
  - `id` (string): ID da conta Instagram
  - `username` (string, opcional): Username da conta Instagram
  - `name` (string, opcional): Nome da conta Instagram
- `pages` (array): Lista de páginas Facebook conectadas
  - `id` (string): ID da página Facebook
  - `name` (string): Nome da página
  - `instagram_business_account` (object, opcional): Conta Instagram Business conectada à página
- `message` (string): Mensagem de confirmação

**Erros Possíveis:**

**400 Bad Request:**
```json
{
  "detail": "State não corresponde ao usuário autenticado"
}
```
ou
```json
{
  "detail": "Erro ao trocar code por token: {...}"
}
```
ou
```json
{
  "detail": "Token de acesso não retornado pela API Meta"
}
```

**401 Unauthorized:**
```json
{
  "detail": "Token de autorização não fornecido"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Erro ao processar callback: ..."
}
```

---

## 🔄 Fluxo Completo de Integração

### Passo 1: Obter Token Firebase

O frontend deve obter um token Firebase válido do usuário autenticado.

### Passo 2: Iniciar OAuth

```javascript
const response = await fetch(
  'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/login',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      redirect_uri: 'https://seu-dominio.com/auth/instagram/callback'
    })
  }
);

const { auth_url } = await response.json();
// Redirecionar usuário para auth_url
window.location.href = auth_url;
```

### Passo 3: Receber Callback do Meta

O Meta redireciona para:
```
https://seu-dominio.com/auth/instagram/callback?code=XXX&state=YYY
```

### Passo 4: Processar Callback

```javascript
// Extrair code e state da URL
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// Chamar API para processar
const response = await fetch(
  'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      code: code,
      state: state,
      redirect_uri: 'https://seu-dominio.com/auth/instagram/callback'
    })
  }
);

const data = await response.json();
// data.api_key - usar para identificar a integração
// data.instagram_accounts - contas Instagram conectadas
// data.pages - páginas Facebook conectadas
```

---

## 📝 Schemas de Dados

### InstagramLoginRequest
```typescript
{
  redirect_uri: string;
}
```

### InstagramLoginResponse
```typescript
{
  auth_url: string;
}
```

### InstagramCallbackRequest
```typescript
{
  code: string;
  state: string;
  redirect_uri: string;
}
```

### InstagramCallbackResponse
```typescript
{
  api_key: string;
  instagram_accounts: InstagramAccount[];
  pages: InstagramPage[];
  message: string;
}
```

### InstagramAccount
```typescript
{
  id: string;
  username?: string;
  name?: string;
}
```

### InstagramPage
```typescript
{
  id: string;
  name: string;
  instagram_business_account?: InstagramAccount;
}
```

---

## 🔐 Permissões Instagram Solicitadas

A API solicita as seguintes 12 permissões do Instagram/Meta:

1. `pages_show_list` - Listar páginas do Facebook
2. `ads_management` - Gerenciar anúncios
3. `ads_read` - Ler dados de anúncios
4. `instagram_basic` - Acesso básico ao Instagram
5. `instagram_manage_comments` - Gerenciar comentários
6. `instagram_manage_insights` - Gerenciar insights e métricas
7. `instagram_content_publish` - Publicar conteúdo
8. `instagram_manage_messages` - Gerenciar mensagens diretas
9. `pages_read_engagement` - Ler engajamento das páginas
10. `pages_manage_ads` - Gerenciar anúncios das páginas
11. `instagram_branded_content_ads_brand` - Gerenciar conteúdo patrocinado
12. `instagram_manage_events` - Gerenciar eventos

---

## ⚠️ Validações Importantes

1. **Token Firebase:** Deve ser válido e não expirado
2. **State:** O `state` no callback deve corresponder ao `user_uid` do token Firebase
3. **Redirect URI:** Deve ser exatamente igual nas duas chamadas (login e callback)
4. **Redirect URI no Meta:** Deve estar configurada nas "Valid OAuth Redirect URIs" do app Meta

---

## 📚 Documentação Adicional

- **Swagger UI:** https://proof-social-instagram-auth-30922479426.us-central1.run.app/docs
- **ReDoc:** https://proof-social-instagram-auth-30922479426.us-central1.run.app/redoc
- **Fluxo Completo:** Ver `FLUXO_COMPLETO.md`
- **Configuração de Callback:** Ver `CALLBACK_URL_CONFIG.md`

---

## 🧪 Exemplos de Código

### JavaScript/TypeScript (Frontend)

```typescript
class InstagramOAuthClient {
  private apiUrl = 'https://proof-social-instagram-auth-30922479426.us-central1.run.app';
  
  async startOAuth(firebaseToken: string, redirectUri: string): Promise<string> {
    const response = await fetch(`${this.apiUrl}/auth/instagram/login`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ redirect_uri: redirectUri })
    });
    
    if (!response.ok) {
      throw new Error(`Failed to start OAuth: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.auth_url;
  }
  
  async processCallback(
    firebaseToken: string,
    code: string,
    state: string,
    redirectUri: string
  ) {
    const response = await fetch(`${this.apiUrl}/auth/instagram/process-callback`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        code,
        state,
        redirect_uri: redirectUri
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to process callback');
    }
    
    return await response.json();
  }
}
```

### Python (Backend/Teste)

```python
import requests

API_URL = "https://proof-social-instagram-auth-30922479426.us-central1.run.app"

def start_oauth(firebase_token: str, redirect_uri: str) -> str:
    response = requests.post(
        f"{API_URL}/auth/instagram/login",
        headers={
            "Authorization": f"Bearer {firebase_token}",
            "Content-Type": "application/json"
        },
        json={"redirect_uri": redirect_uri}
    )
    response.raise_for_status()
    return response.json()["auth_url"]

def process_callback(
    firebase_token: str,
    code: str,
    state: str,
    redirect_uri: str
) -> dict:
    response = requests.post(
        f"{API_URL}/auth/instagram/process-callback",
        headers={
            "Authorization": f"Bearer {firebase_token}",
            "Content-Type": "application/json"
        },
        json={
            "code": code,
            "state": state,
            "redirect_uri": redirect_uri
        }
    )
    response.raise_for_status()
    return response.json()
```

---

## 📞 Suporte

Para dúvidas ou problemas:
- Verifique a documentação Swagger em `/docs`
- Consulte `FLUXO_COMPLETO.md` para entender o fluxo detalhado
- Verifique os logs do Cloud Run no console do Google Cloud

