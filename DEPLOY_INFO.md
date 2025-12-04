# 🚀 Informações de Deploy

## ✅ Deploy Realizado com Sucesso

**Data:** 2025-12-04  
**Projeto:** proof-social-ai  
**Região:** us-central1  
**Serviço:** proof-social-instagram-auth

## 🌐 URL do Serviço

**URL Base:**
```
https://proof-social-instagram-auth-30922479426.us-central1.run.app
```

## 📍 Endpoints Disponíveis

### Endpoints Públicos

1. **GET /** - Informações do serviço
   ```
   https://proof-social-instagram-auth-30922479426.us-central1.run.app/
   ```

2. **GET /health** - Health check
   ```
   https://proof-social-instagram-auth-30922479426.us-central1.run.app/health
   ```

3. **GET /docs** - Documentação Swagger UI
   ```
   https://proof-social-instagram-auth-30922479426.us-central1.run.app/docs
   ```

4. **GET /redoc** - Documentação ReDoc
   ```
   https://proof-social-instagram-auth-30922479426.us-central1.run.app/redoc
   ```

### Endpoints OAuth (Requerem Autenticação)

1. **POST /auth/instagram/login** - Iniciar fluxo OAuth
   ```
   POST https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/login
   Headers:
     Authorization: Bearer {firebase_token}
     Content-Type: application/json
   Body:
     {
       "redirect_uri": "https://seu-app.com/auth/instagram/callback"
     }
   ```

2. **POST /auth/instagram/process-callback** - Processar callback OAuth
   ```
   POST https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback
   Headers:
     Authorization: Bearer {firebase_token}
     Content-Type: application/json
   Body:
     {
       "code": "AUTHORIZATION_CODE",
       "state": "USER_UID",
       "redirect_uri": "https://seu-app.com/auth/instagram/callback"
     }
   ```

## 🔧 Configurações do Deploy

- **Plataforma:** Cloud Run (managed)
- **Região:** us-central1
- **Autenticação:** Pública (allow-unauthenticated)
- **Variáveis de Ambiente:**
  - `GOOGLE_CLOUD_PROJECT=proof-social-ai`

## 📦 Imagem Docker

**Imagem:** `gcr.io/proof-social-ai/proof-social-instagram-auth:latest`

**Digest:** `sha256:87719414b969a26ef4c2436626cbdd941e3db890393030dd937fde91f4c5ac8a`

## ✅ Status

- ✅ Build bem-sucedido
- ✅ Imagem pushada para Container Registry
- ✅ Serviço deployado no Cloud Run
- ✅ Serviço está rodando e recebendo tráfego

## 🧪 Testes

### Teste 1: Health Check
```bash
curl https://proof-social-instagram-auth-30922479426.us-central1.run.app/health
```

**Resposta esperada:**
```json
{
  "status": "healthy"
}
```

### Teste 2: Informações do Serviço
```bash
curl https://proof-social-instagram-auth-30922479426.us-central1.run.app/
```

**Resposta esperada:**
```json
{
  "message": "Proof Social Instagram Auth API",
  "version": "1.0.0",
  "status": "running"
}
```

## 📝 Próximos Passos

1. ✅ Deploy realizado
2. ⏳ Testar endpoints OAuth com tokens Firebase reais
3. ⏳ Configurar redirect URIs no app Meta
4. ⏳ Testar fluxo completo de autenticação

## 🔗 Links Úteis

- **Console Cloud Run:** https://console.cloud.google.com/run/detail/us-central1/proof-social-instagram-auth?project=proof-social-ai
- **Logs:** https://console.cloud.google.com/run/detail/us-central1/proof-social-instagram-auth/logs?project=proof-social-ai
- **Métricas:** https://console.cloud.google.com/run/detail/us-central1/proof-social-instagram-auth/metrics?project=proof-social-ai

