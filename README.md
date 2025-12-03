# Proof Social - Instagram OAuth API

API para autenticação OAuth com Meta/Instagram, permitindo integração de contas Instagram Business com permissões completas para gerenciamento de conteúdo, insights, comentários e mensagens.

## 🎯 Objetivo

Implementar endpoints OAuth Meta/Instagram para completar o fluxo de autenticação com Firebase Auth, permitindo que usuários conectem suas contas Instagram Business e gerenciem conteúdo, insights, comentários e mensagens.

## ✅ Funcionalidades

### Endpoints Implementados

1. **POST /auth/instagram/login** - Gera URL de autorização Meta/Instagram
2. **POST /auth/instagram/process-callback** - Processa callback OAuth e configura integração

### Permissões Instagram/Meta

A aplicação solicita as seguintes permissões:

- `pages_show_list` - Listar páginas do Facebook
- `ads_management` - Gerenciar anúncios
- `ads_read` - Ler dados de anúncios
- `instagram_basic` - Acesso básico ao Instagram
- `instagram_manage_comments` - Gerenciar comentários
- `instagram_manage_insights` - Gerenciar insights e métricas
- `instagram_content_publish` - Publicar conteúdo
- `instagram_manage_messages` - Gerenciar mensagens diretas
- `pages_read_engagement` - Ler engajamento das páginas
- `pages_manage_ads` - Gerenciar anúncios das páginas
- `instagram_branded_content_ads_brand` - Gerenciar conteúdo patrocinado
- `instagram_manage_events` - Gerenciar eventos

## 🚀 Como Usar

### 1. Configuração Inicial

#### Variáveis de Ambiente

```bash
GOOGLE_CLOUD_PROJECT=proof-social
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

#### Secret Manager

Configure os seguintes secrets no Google Cloud Secret Manager:

- `proof-social-meta-app-id` - App ID do Meta
- `proof-social-meta-app-secret` - App Secret do Meta

### 2. Iniciar Fluxo OAuth

```bash
curl -X POST "https://your-api-url/auth/instagram/login" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uri": "https://your-app.com/auth/instagram/callback"
  }'
```

**Resposta:**

```json
{
  "auth_url": "https://www.facebook.com/v20.0/dialog/oauth?client_id=...&redirect_uri=...&state=user_uid&response_type=code&scope=pages_show_list,ads_management,..."
}
```

### 3. Processar Callback

```bash
curl -X POST "https://your-api-url/auth/instagram/process-callback" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "AUTHORIZATION_CODE",
    "state": "USER_UID"
  }'
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

## 📁 Estrutura do Projeto

```
proof-social-instagram-auth/
├── main.py                 # Aplicação FastAPI principal
├── requirements.txt        # Dependências Python
├── README.md              # Esta documentação
├── core/
│   ├── __init__.py
│   └── security.py        # Validação Firebase e Secret Manager
├── routes/
│   ├── __init__.py
│   └── auth.py            # Endpoints OAuth Instagram
└── schemas/
    ├── __init__.py
    └── instagram.py       # Schemas Pydantic
```

## 🛠️ Instalação

### Configuração Inicial do Repositório

```bash
# Executar script de setup
./setup_repo.sh

# Ou manualmente:
git init
git add .
git commit -m "Initial commit: Proof Social Instagram OAuth API"
git remote add origin https://github.com/proof-social/proof-social-instagram-auth.git
git branch -M main
git push -u origin main
```

**Nota:** Certifique-se de criar o repositório `proof-social-instagram-auth` na organização `proof-social` no GitHub antes de fazer o push.

### Instalação Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 📝 Desenvolvimento

### Executar Localmente

```bash
# Configurar variáveis de ambiente
export GOOGLE_CLOUD_PROJECT=proof-social
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Executar servidor de desenvolvimento
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Deploy no Google Cloud Run

```bash
# Build e deploy
gcloud builds submit --tag gcr.io/proof-social/proof-social-instagram-auth
gcloud run deploy proof-social-instagram-auth \
  --image gcr.io/proof-social-ai/proof-social-instagram-auth \
  --platform managed \
  --region us-central1
```

## 📚 Documentação da API

A documentação interativa da API está disponível em:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## 🔗 Links Úteis

- [Meta Graph API Documentation](https://developers.facebook.com/docs/graph-api)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)

## 📄 Licença

Este projeto é propriedade da Proof Social.

