# 🔗 Configuração de Callback URL - Meta OAuth

## 📋 Entendendo o Fluxo de Callback

No fluxo OAuth, existem **duas URLs diferentes**:

1. **URL de Autorização (gerada pelo backend)** - Usuário acessa esta URL no Meta
2. **Redirect URI (callback)** - URL para onde o Meta redireciona após autorização

## 🔄 Como Funciona

```
1. Frontend → POST /auth/instagram/login
   Body: { "redirect_uri": "https://seu-app.com/auth/instagram/callback" }

2. Backend → Gera URL de autorização Meta:
   https://www.facebook.com/v20.0/dialog/oauth?
     client_id=4109658012632973&
     redirect_uri=https://seu-app.com/auth/instagram/callback&  ← Esta URL
     state=user_uid&
     response_type=code&
     scope=...

3. Usuário → Acessa URL do Meta e autoriza

4. Meta → Redireciona para redirect_uri:
   https://seu-app.com/auth/instagram/callback?  ← Meta redireciona aqui
     code=AUTHORIZATION_CODE&
     state=USER_UID

5. Frontend → Recebe callback e chama:
   POST /auth/instagram/process-callback
```

## ✅ URL de Callback que Você Precisa Configurar

### No App Meta (Facebook Developers)

Você precisa adicionar a URL de callback nas **"Valid OAuth Redirect URIs"** do seu app Meta.

**URLs que você deve configurar:**

1. **URL do seu frontend (produção):**
   ```
   https://seu-dominio.com/auth/instagram/callback
   ```

2. **URL do seu frontend (desenvolvimento):**
   ```
   http://localhost:3000/auth/instagram/callback
   ```
   ou
   ```
   https://seu-dominio-dev.com/auth/instagram/callback
   ```

### ⚠️ Importante

- A URL de callback **NÃO é a URL da API** (Cloud Run)
- A URL de callback **É a URL do seu frontend** onde o Meta vai redirecionar
- O frontend recebe o `code` e então chama a API para processar

## 🔧 Como Configurar no Facebook Developers

1. Acesse: https://developers.facebook.com/apps/4109658012632973/settings/basic/

2. Vá em **"Settings" → "Basic"**

3. Role até **"Valid OAuth Redirect URIs"**

4. Adicione suas URLs de callback:
   ```
   https://seu-dominio.com/auth/instagram/callback
   http://localhost:3000/auth/instagram/callback
   ```

5. Clique em **"Save Changes"**

## 📝 Exemplo Prático

### Se seu frontend está em:
- **Produção:** `https://app.proof-social.com`
- **Desenvolvimento:** `http://localhost:3000`

### URLs de callback a configurar:
```
https://app.proof-social.com/auth/instagram/callback
http://localhost:3000/auth/instagram/callback
```

### Quando chamar a API:

**1. Iniciar OAuth:**
```bash
POST https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/login
{
  "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
}
```

**2. Meta redireciona para:**
```
https://app.proof-social.com/auth/instagram/callback?code=XXX&state=YYY
```

**3. Frontend processa e chama:**
```bash
POST https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback
{
  "code": "XXX",
  "state": "YYY",
  "redirect_uri": "https://app.proof-social.com/auth/instagram/callback"
}
```

## 🎯 Resumo

- **URL da API (Cloud Run):** `https://proof-social-instagram-auth-30922479426.us-central1.run.app`
- **URL de Callback (Frontend):** `https://seu-dominio.com/auth/instagram/callback`
- **Onde configurar:** Facebook Developers → App Settings → Valid OAuth Redirect URIs

## ⚠️ Erro Comum

Se você receber erro:
```
"redirect_uri_mismatch"
```

Isso significa que a URL que você passou no `redirect_uri` não está configurada nas "Valid OAuth Redirect URIs" do app Meta.

**Solução:** Adicione a URL exata (incluindo protocolo http/https e porta) nas configurações do app Meta.

