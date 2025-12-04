# 🔄 Fluxo Completo - OAuth Instagram/Meta

Este documento descreve o fluxo completo de autenticação OAuth Instagram/Meta implementado no projeto.

## 📋 Visão Geral

O fluxo permite que usuários conectem suas contas Instagram Business através do Meta (Facebook), obtendo permissões para gerenciar conteúdo, insights, comentários e mensagens.

## 🎯 Componentes Principais

1. **Frontend** - Aplicação cliente (não incluída neste repositório)
2. **Backend API** - FastAPI (`main.py`, `routes/auth.py`)
3. **Firebase Auth** - Autenticação do usuário
4. **Google Cloud Secret Manager** - Armazenamento seguro de credenciais
5. **Firestore** - Banco de dados para integrações
6. **Meta/Instagram API** - API externa para OAuth

## 🔄 Fluxo Passo a Passo

### **FASE 1: Inicialização do Fluxo OAuth**

```
┌─────────┐                    ┌──────────┐                    ┌─────────┐
│Frontend│                    │ Backend  │                    │  Meta   │
│        │                    │   API    │                    │   API   │
└───┬────┘                    └────┬─────┘                    └────┬────┘
    │                                │                                │
    │ 1. POST /auth/instagram/login  │                                │
    │    Headers:                    │                                │
    │    - Authorization: Bearer      │                                │
    │      {firebase_token}          │                                │
    │    Body:                       │                                │
    │    {                          │                                │
    │      "redirect_uri": "..."    │                                │
    │    }                          │                                │
    ├───────────────────────────────>│                                │
    │                                │                                │
    │                                │ 2. Valida Firebase Token      │
    │                                │    (core/security.py)          │
    │                                │    - Verifica token válido     │
    │                                │    - Extrai user_uid           │
    │                                │                                │
    │                                │ 3. Busca Configurações Meta   │
    │                                │    (Secret Manager)            │
    │                                │    - proof-social-meta-app-id  │
    │                                │    - proof-social-meta-app-    │
    │                                │      secret                    │
    │                                │                                │
    │                                │ 4. Gera URL de Autorização    │
    │                                │    - client_id (App ID)        │
    │                                │    - redirect_uri              │
    │                                │    - state = user_uid          │
    │                                │    - scope = 12 permissões     │
    │                                │                                │
    │ 5. Response:                  │                                │
    │    {                          │                                │
    │      "auth_url": "https://..."│                                │
    │    }                          │                                │
    │<───────────────────────────────┤                                │
    │                                │                                │
    │ 6. Redireciona usuário        │                                │
    │    para auth_url              │                                │
    │─────────────────────────────────────────────────────────────────>│
```

**Detalhes da Fase 1:**

1. **Frontend faz requisição:**
   ```bash
   POST /auth/instagram/login
   Authorization: Bearer {firebase_token}
   {
     "redirect_uri": "https://seu-app.com/auth/instagram/callback"
   }
   ```

2. **Backend valida token Firebase:**
   - `verify_firebase_token()` valida o token
   - Extrai `user_uid` do token decodificado
   - Se inválido, retorna erro 401

3. **Backend busca configurações:**
   - `get_meta_config()` busca do Secret Manager:
     - `proof-social-meta-app-id` → App ID do Meta
     - `proof-social-meta-app-secret` → App Secret do Meta

4. **Backend gera URL de autorização:**
   ```python
   auth_url = (
       f"https://www.facebook.com/v20.0/dialog/oauth?"
       f"client_id={app_id}&"
       f"redirect_uri={redirect_uri}&"
       f"state={user_uid}&"  # user_uid como state
       f"response_type=code&"
       f"scope={scopes}"  # 12 permissões Instagram
   )
   ```

5. **Frontend recebe `auth_url` e redireciona usuário**

---

### **FASE 2: Autorização do Usuário no Meta**

```
┌─────────┐                    ┌──────────┐                    ┌─────────┐
│Frontend│                    │ Backend  │                    │  Meta   │
│        │                    │   API    │                    │   API   │
└───┬────┘                    └────┬─────┘                    └────┬────┘
    │                                │                                │
    │                                │                                │
    │ 7. Usuário autoriza app        │                                │
    │    no Meta (interface web)     │                                │
    │                                │                                │
    │                                │                                │
    │                                │                                │
    │ 8. Meta redireciona para       │                                │
    │    redirect_uri com code      │                                │
    │                                │                                │
    │<─────────────────────────────────────────────────────────────────┤
    │                                │                                │
    │    redirect_uri?code=XXX&      │                                │
    │    state=user_uid              │                                │
    │                                │                                │
```

**Detalhes da Fase 2:**

1. **Usuário vê tela de autorização do Meta:**
   - Lista de permissões solicitadas (12 permissões Instagram)
   - Botão "Continuar" ou "Cancelar"

2. **Usuário autoriza:**
   - Meta gera um `authorization_code` temporário
   - Meta redireciona para `redirect_uri` com:
     - `code`: código de autorização
     - `state`: user_uid (para validação)

3. **Frontend recebe callback:**
   ```
   https://seu-app.com/auth/instagram/callback?
     code=AUTHORIZATION_CODE&
     state=USER_UID
   ```

---

### **FASE 3: Processamento do Callback**

```
┌─────────┐                    ┌──────────┐                    ┌─────────┐
│Frontend│                    │ Backend  │                    │  Meta   │
│        │                    │   API    │                    │   API   │
└───┬────┘                    └────┬─────┘                    └────┬────┘
    │                                │                                │
    │ 9. POST /auth/instagram/      │                                │
    │    process-callback           │                                │
    │    Headers:                   │                                │
    │    - Authorization: Bearer     │                                │
    │      {firebase_token}         │                                │
    │    Body:                      │                                │
    │    {                         │                                │
    │      "code": "XXX",          │                                │
    │      "state": "user_uid",   │                                │
    │      "redirect_uri": "..."   │                                │
    │    }                         │                                │
    ├───────────────────────────────>│                                │
    │                                │                                │
    │                                │ 10. Valida Firebase Token     │
    │                                │     e State                   │
    │                                │     - Token válido?           │
    │                                │     - state == user_uid?       │
    │                                │                                │
    │                                │ 11. Troca code por token      │
    │                                │     (curta duração)            │
    │                                ├───────────────────────────────>│
    │                                │                                │
    │                                │     POST /oauth/access_token  │
    │                                │     {                        │
    │                                │       client_id,             │
    │                                │       client_secret,         │
    │                                │       code,                  │
    │                                │       redirect_uri            │
    │                                │     }                        │
    │                                │                                │
    │                                │<───────────────────────────────┤
    │                                │                                │
    │                                │     Response:                 │
    │                                │     {                        │
    │                                │       "access_token": "..."  │
    │                                │     }                        │
    │                                │                                │
    │                                │ 12. Converte para token        │
    │                                │     de longa duração          │
    │                                ├───────────────────────────────>│
    │                                │                                │
    │                                │     POST /oauth/access_token  │
    │                                │     {                        │
    │                                │       grant_type:            │
    │                                │         "fb_exchange_token", │
    │                                │       fb_exchange_token:    │
    │                                │         {short_token}        │
    │                                │     }                        │
    │                                │                                │
    │                                │<───────────────────────────────┤
    │                                │                                │
    │                                │     Response:                 │
    │                                │     {                        │
    │                                │       "access_token": "..."  │
    │                                │       (longa duração)         │
    │                                │     }                        │
    │                                │                                │
    │                                │ 13. Salva token no            │
    │                                │     Secret Manager            │
    │                                │     - proof-social-          │
    │                                │       instagram-{user_uid}    │
    │                                │                                │
    │                                │ 14. Busca páginas e contas    │
    │                                │     Instagram                 │
    │                                ├───────────────────────────────>│
    │                                │                                │
    │                                │     GET /me/accounts          │
    │                                │     ?access_token=...         │
    │                                │     &fields=id,name,          │
    │                                │     instagram_business_       │
    │                                │     account{id,username}      │
    │                                │                                │
    │                                │<───────────────────────────────┤
    │                                │                                │
    │                                │     Response:                 │
    │                                │     {                        │
    │                                │       "data": [              │
    │                                │         {                    │
    │                                │           "id": "...",       │
    │                                │           "name": "...",     │
    │                                │           "instagram_       │
    │                                │           business_account": │
    │                                │             {...}           │
    │                                │         }                    │
    │                                │       ]                      │
    │                                │     }                        │
    │                                │                                │
    │                                │ 15. Gera API Key única        │
    │                                │     (UUID)                    │
    │                                │                                │
    │                                │ 16. Salva integração no       │
    │                                │     Firestore                 │
    │                                │     Collection: integrations │
    │                                │     Document: {user_uid}      │
    │                                │     {                        │
    │                                │       user_uid,              │
    │                                │       platform: "instagram", │
    │                                │       api_key,                │
    │                                │       status: "active",      │
    │                                │       instagram_accounts,    │
    │                                │       pages,                 │
    │                                │       created_at              │
    │                                │     }                        │
    │                                │                                │
    │ 17. Response:                 │                                │
    │     {                         │                                │
    │       "api_key": "uuid",      │                                │
    │       "instagram_accounts": [],│                                │
    │       "pages": [],            │                                │
    │       "message": "..."        │                                │
    │     }                         │                                │
    │<───────────────────────────────┤                                │
    │                                │                                │
```

**Detalhes da Fase 3:**

1. **Frontend envia code e state:**
   ```bash
   POST /auth/instagram/process-callback
   Authorization: Bearer {firebase_token}
   {
     "code": "AUTHORIZATION_CODE",
     "state": "USER_UID",
     "redirect_uri": "https://seu-app.com/auth/instagram/callback"
   }
   ```

2. **Backend valida:**
   - Token Firebase válido?
   - `state` corresponde ao `user_uid` do token?

3. **Troca code por access_token (curta duração):**
   ```http
   GET https://graph.facebook.com/v20.0/oauth/access_token?
     client_id={app_id}&
     client_secret={app_secret}&
     redirect_uri={redirect_uri}&
     code={code}
   ```

4. **Converte para token de longa duração:**
   ```http
   GET https://graph.facebook.com/v20.0/oauth/access_token?
     grant_type=fb_exchange_token&
     client_id={app_id}&
     client_secret={app_secret}&
     fb_exchange_token={short_token}
   ```

5. **Salva token no Secret Manager:**
   - Secret ID: `proof-social-instagram-{user_uid}`
   - Valor: token de longa duração

6. **Busca páginas e contas Instagram:**
   ```http
   GET https://graph.facebook.com/v20.0/me/accounts?
     access_token={long_token}&
     fields=id,name,instagram_business_account{id,username}
   ```

7. **Gera API Key única (UUID)**

8. **Salva no Firestore:**
   ```javascript
   {
     user_uid: "abc123",
     platform: "instagram",
     api_key: "uuid-gerado",
     status: "active",
     instagram_accounts: [
       {
         id: "17841405309211844",
         username: "minha_conta",
         name: "Minha Conta"
       }
     ],
     pages: [
       {
         id: "123456789",
         name: "Minha Página",
         instagram_business_account_id: "17841405309211844"
       }
     ],
     created_at: Timestamp
   }
   ```

9. **Retorna resposta completa ao frontend**

---

## 🔐 Segurança em Cada Etapa

### **Validação Firebase Token**
- Token verificado com Firebase Admin SDK
- `user_uid` extraído do token
- Proteção contra tokens inválidos/expirados

### **Validação de State**
- `state` deve corresponder ao `user_uid`
- Previne ataques CSRF
- Garante que o callback é para o usuário correto

### **Armazenamento Seguro**
- Tokens salvos no Secret Manager (criptografados)
- Isolamento por usuário (cada usuário tem seu próprio secret)
- API keys únicas por integração

### **Isolamento Multi-Tenant**
- Cada usuário tem suas próprias credenciais
- Sem acesso cruzado entre usuários
- Dados isolados no Firestore

---

## 📊 Permissões Instagram Solicitadas

O fluxo solicita as seguintes 12 permissões:

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

## 🔄 Fluxo Visual Simplificado

```
[Usuário] 
    │
    ├─> [Frontend] 
    │      │
    │      ├─> POST /auth/instagram/login
    │      │      │
    │      │      └─> [Backend]
    │      │             │
    │      │             ├─> Valida Firebase Token
    │      │             ├─> Busca App ID/Secret (Secret Manager)
    │      │             └─> Retorna auth_url
    │      │
    │      └─> Redireciona para Meta
    │             │
    │             └─> [Meta OAuth]
    │                    │
    │                    ├─> Usuário autoriza
    │                    └─> Redireciona com code
    │                           │
    │                           └─> [Frontend recebe callback]
    │                                  │
    │                                  ├─> POST /auth/instagram/process-callback
    │                                  │      │
    │                                  │      └─> [Backend]
    │                                  │             │
    │                                  │             ├─> Valida token e state
    │                                  │             ├─> Troca code por token
    │                                  │             ├─> Converte para longa duração
    │                                  │             ├─> Salva token (Secret Manager)
    │                                  │             ├─> Busca contas Instagram
    │                                  │             ├─> Gera API key
    │                                  │             └─> Salva integração (Firestore)
    │                                  │
    │                                  └─> Recebe api_key e dados
    │
    └─> [Usuário pode usar api_key para chamadas à API]
```

---

## 📝 Exemplo de Uso Completo

### 1. Iniciar Fluxo

```bash
curl -X POST "https://api.proof-social.com/auth/instagram/login" \
  -H "Authorization: Bearer FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
  }'
```

**Resposta:**
```json
{
  "auth_url": "https://www.facebook.com/v20.0/dialog/oauth?client_id=4109658012632973&redirect_uri=https://app.proof-social.com/auth/instagram/callback&state=user123&response_type=code&scope=pages_show_list,ads_management,..."
}
```

### 2. Usuário autoriza no Meta

Usuário é redirecionado para Meta, autoriza, e Meta redireciona para:
```
https://app.proof-social.com/auth/instagram/callback?code=AUTHORIZATION_CODE&state=user123
```

### 3. Processar Callback

```bash
curl -X POST "https://api.proof-social.com/auth/instagram/process-callback" \
  -H "Authorization: Bearer FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AUTHORIZATION_CODE",
    "state": "user123",
    "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
  }'
```

**Resposta:**
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

---

## 🎯 Resultado Final

Após o fluxo completo:

1. ✅ Token de acesso salvo no Secret Manager
2. ✅ Integração salva no Firestore
3. ✅ API key gerada e retornada
4. ✅ Contas Instagram identificadas
5. ✅ Páginas Facebook conectadas listadas
6. ✅ Usuário pode usar `api_key` para chamadas à API

---

## 🔧 Componentes Técnicos

### **Arquivos Principais**

- `main.py` - Aplicação FastAPI
- `routes/auth.py` - Endpoints OAuth
- `core/security.py` - Validação Firebase e Secret Manager
- `schemas/instagram.py` - Schemas Pydantic

### **Serviços Utilizados**

- **Firebase Auth** - Autenticação de usuários
- **Google Cloud Secret Manager** - Armazenamento de secrets
- **Firestore** - Banco de dados
- **Meta Graph API** - API OAuth e dados Instagram

---

## ⚠️ Tratamento de Erros

O fluxo trata os seguintes erros:

- ❌ Token Firebase inválido → 401 Unauthorized
- ❌ State não corresponde → 400 Bad Request
- ❌ Code inválido/expirado → 400 Bad Request
- ❌ Erro ao trocar code → 400 Bad Request
- ❌ Erro ao salvar token → 500 Internal Server Error
- ❌ Erro ao buscar contas → 500 Internal Server Error

Todos os erros são logados para auditoria.

