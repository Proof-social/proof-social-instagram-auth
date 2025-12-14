# 📋 Contrato de API - Frontend Integration

## 🌐 URL Base da API

```
https://proof-social-instagram-auth-30922479426.us-central1.run.app
```

---

## 🔐 Autenticação

Todos os endpoints requerem autenticação via **Firebase Auth Token** no header `Authorization`:

```
Authorization: Bearer {firebase_token}
```

O `firebase_token` deve ser obtido do Firebase Auth no frontend.

---

## 📍 Endpoints

### 1. POST /auth/instagram/login - Iniciar Fluxo OAuth

**Descrição:** Gera URL de autorização Meta/Instagram para iniciar o fluxo OAuth

**Método:** `POST`  
**Path:** `/auth/instagram/login`  
**Autenticação:** ✅ Requerida (Firebase Token)

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
- `redirect_uri` (string, obrigatório): URL do frontend para onde o Meta redirecionará após autorização. Deve estar configurada nas "Valid OAuth Redirect URIs" do app Meta.

**Response 200:**
```json
{
  "auth_url": "https://www.facebook.com/v20.0/dialog/oauth?client_id=...&redirect_uri=...&state=...&response_type=code&scope=..."
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

### 2. POST /auth/instagram/process-callback - Processar Callback OAuth

**Descrição:** Processa o callback do Meta após autorização e retorna as contas Instagram do usuário

**Método:** `POST`  
**Path:** `/auth/instagram/process-callback`  
**Autenticação:** ✅ Requerida (Firebase Token)

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
  "message": "Integração Instagram configurada com sucesso",
  "status": "success",
  "redirect_url": "https://seu-dominio.com/auth/instagram/callback?data={JSON_ENCODED}"
}
```

**Response Fields:**
- `api_key` (string, UUID): Chave única gerada para esta integração. Use esta chave para identificar a integração em chamadas futuras.
- `instagram_accounts` (array): Lista de contas Instagram Business conectadas
  - `id` (string): ID da conta Instagram
  - `username` (string, opcional): Username da conta Instagram
  - `name` (string, opcional): Nome da conta Instagram
- `message` (string): Mensagem de confirmação
- `status` (string): Status da operação ("success")
- `redirect_url` (string, opcional): URL com os dados codificados na query string (para uso opcional)

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

O frontend deve obter um token Firebase válido do usuário autenticado:

```javascript
import { getAuth } from 'firebase/auth';

const auth = getAuth();
const user = auth.currentUser;
const firebaseToken = await user.getIdToken();
```

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

if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail || 'Erro ao iniciar OAuth');
}

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

Na página de callback do frontend:

```javascript
// Extrair code e state da URL
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// Verificar se já temos dados (após redirect opcional)
const dataParam = urlParams.get('data');
if (dataParam) {
  // Dados já foram processados, usar diretamente
  const data = JSON.parse(decodeURIComponent(dataParam));
  console.log('Contas Instagram:', data.instagram_accounts);
  // Salvar dados e redirecionar para dashboard
  return;
}

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

if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail || 'Erro ao processar callback');
}

const data = await response.json();

// data.api_key - usar para identificar a integração
// data.instagram_accounts - contas Instagram conectadas
console.log('API Key:', data.api_key);
console.log('Contas Instagram:', data.instagram_accounts);
```

---

## 💻 Exemplos de Implementação

### React/Next.js

```tsx
// pages/auth/instagram/callback.tsx
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { getAuth } from 'firebase/auth';

export default function InstagramCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [accounts, setAccounts] = useState<any[]>([]);

  useEffect(() => {
    async function processCallback() {
      const urlParams = new URLSearchParams(window.location.search);
      
      // Verificar se já temos dados (após redirect opcional)
      const dataParam = urlParams.get('data');
      if (dataParam) {
        try {
          const data = JSON.parse(decodeURIComponent(dataParam));
          setAccounts(data.instagram_accounts);
          setStatus('success');
          
          // Salvar no estado global ou Firestore
          await saveIntegrationData(data);
          
          // Redirecionar após 2 segundos
          setTimeout(() => {
            router.push('/dashboard?integration=success');
          }, 2000);
        } catch (error) {
          console.error('Erro ao processar dados:', error);
          setStatus('error');
        }
        return;
      }

      // Primeiro callback do Meta - temos code e state
      const code = urlParams.get('code');
      const state = urlParams.get('state');

      if (!code || !state) {
        setStatus('error');
        return;
      }

      try {
        // Obter token Firebase
        const auth = getAuth();
        const user = auth.currentUser;
        if (!user) {
          throw new Error('Usuário não autenticado');
        }
        const firebaseToken = await user.getIdToken();

        // Chamar API do backend
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
              redirect_uri: `${window.location.origin}/auth/instagram/callback`
            })
          }
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Erro ao processar callback');
        }

        const data = await response.json();
        
        // Exibir contas na tela
        setAccounts(data.instagram_accounts);
        setStatus('success');

        // Salvar dados
        await saveIntegrationData(data);

        // Opção 1: Usar redirect_url (opcional)
        // if (data.redirect_url) {
        //   window.location.href = data.redirect_url;
        //   return;
        // }

        // Opção 2: Redirecionar manualmente após exibir dados
        setTimeout(() => {
          router.push('/dashboard?integration=success');
        }, 3000);

      } catch (error) {
        console.error('Erro ao processar callback:', error);
        setStatus('error');
      }
    }

    processCallback();
  }, [router, searchParams]);

  if (status === 'processing') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Processando integração...</p>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="text-red-500 text-4xl mb-4">❌</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Erro ao processar integração</h1>
          <p className="text-gray-600">Por favor, tente novamente.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
        <div className="text-center mb-6">
          <div className="text-green-500 text-4xl mb-4">✅</div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">
            Integração Concluída!
          </h1>
          <p className="text-gray-600">
            Suas contas Instagram foram conectadas com sucesso.
          </p>
        </div>

        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-3">
            Contas Conectadas ({accounts.length})
          </h2>
          <div className="space-y-2">
            {accounts.map((account) => (
              <div
                key={account.id}
                className="flex items-center p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex-1">
                  <p className="font-medium text-gray-800">
                    {account.username || account.name || 'Conta Instagram'}
                  </p>
                  <p className="text-sm text-gray-500">ID: {account.id}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-center">
          <p className="text-sm text-gray-500 mb-4">
            Redirecionando para o dashboard...
          </p>
        </div>
      </div>
    </div>
  );
}

async function saveIntegrationData(data: any) {
  // Implementar salvamento no Firestore ou estado global
  // Exemplo:
  // await firestore.collection('integrations').doc(user.uid).set(data);
}
```

### JavaScript Vanilla

```javascript
// callback.html
async function handleCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  
  // Verificar se já temos dados
  const dataParam = urlParams.get('data');
  if (dataParam) {
    const data = JSON.parse(decodeURIComponent(dataParam));
    displayAccounts(data.instagram_accounts);
    return;
  }

  // Primeiro callback
  const code = urlParams.get('code');
  const state = urlParams.get('state');

  if (!code || !state) {
    showError('Code ou state não encontrado');
    return;
  }

  try {
    // Obter token Firebase
    const firebaseToken = await getFirebaseToken();

    // Chamar API
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
          redirect_uri: window.location.href.split('?')[0]
        })
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Erro ao processar callback');
    }

    const data = await response.json();
    
    // Exibir contas na tela
    displayAccounts(data.instagram_accounts);
    
    // Salvar dados
    await saveToFirestore(data);

  } catch (error) {
    console.error('Erro:', error);
    showError(error.message);
  }
}

function displayAccounts(accounts) {
  const container = document.getElementById('accounts-container');
  container.innerHTML = `
    <h2>Contas Conectadas (${accounts.length})</h2>
    ${accounts.map(account => `
      <div class="account-card">
        <p><strong>${account.username || account.name || 'Conta Instagram'}</strong></p>
        <p class="text-sm">ID: ${account.id}</p>
      </div>
    `).join('')}
  `;
}

// Executar quando a página carregar
window.addEventListener('DOMContentLoaded', handleCallback);
```

---

## 📝 Schemas TypeScript

```typescript
// Tipos para uso no frontend

interface InstagramLoginRequest {
  redirect_uri: string;
}

interface InstagramLoginResponse {
  auth_url: string;
}

interface InstagramCallbackRequest {
  code: string;
  state: string;
  redirect_uri: string;
}

interface InstagramAccount {
  id: string;
  username?: string;
  name?: string;
}

interface InstagramCallbackResponse {
  api_key: string;
  instagram_accounts: InstagramAccount[];
  message: string;
  status: string;
  redirect_url?: string;
}
```

---

## ⚠️ Validações Importantes

1. **Token Firebase:** Deve ser válido e não expirado
2. **State:** O `state` no callback deve corresponder ao `user_uid` do token Firebase
3. **Redirect URI:** Deve ser exatamente igual nas duas chamadas (login e callback)
4. **Redirect URI no Meta:** Deve estar configurada nas "Valid OAuth Redirect URIs" do app Meta

---

## 🔗 URLs Importantes

- **API Base:** `https://proof-social-instagram-auth-30922479426.us-central1.run.app`
- **Endpoint Login:** `POST /auth/instagram/login`
- **Endpoint Callback:** `POST /auth/instagram/process-callback`
- **Documentação Swagger:** `https://proof-social-instagram-auth-30922479426.us-central1.run.app/docs`
- **ReDoc:** `https://proof-social-instagram-auth-30922479426.us-central1.run.app/redoc`

---

## 🎯 Resumo do Fluxo

1. **Frontend** → Chama `POST /auth/instagram/login` → Recebe `auth_url`
2. **Frontend** → Redireciona usuário para `auth_url` (Meta)
3. **Usuário** → Autoriza no Meta
4. **Meta** → Redireciona para `redirect_uri` com `code` e `state`
5. **Frontend** → Chama `POST /auth/instagram/process-callback` com `code` e `state`
6. **Backend** → Processa, salva token, busca contas Instagram
7. **Backend** → Retorna JSON com `api_key` e `instagram_accounts`
8. **Frontend** → Exibe contas na tela de callback

---

## 📞 Suporte

Para dúvidas ou problemas:
- Verifique a documentação Swagger em `/docs`
- Consulte `FLUXO_COMPLETO.md` para entender o fluxo detalhado
- Verifique os logs do Cloud Run no console do Google Cloud

