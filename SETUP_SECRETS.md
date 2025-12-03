# Configuração de Secrets - Google Cloud Secret Manager

## 📋 Informações dos Secrets

- **App ID:** `4109658012632973`
- **App Secret:** `40a3ed6ead74584405a2fc7163b17652`
- **Projeto:** `proof-social-ai`

## 🔧 Opção 1: Via Console do Google Cloud

1. Acesse: https://console.cloud.google.com/security/secret-manager?project=proof-social-ai
2. Clique em **"CREATE SECRET"**
3. Crie os seguintes secrets:

### Secret 1: proof-social-ai-meta-app-id
- **Nome:** `proof-social-ai-meta-app-id`
- **Valor:** `4109658012632973`
- **Replicação:** Automatic

### Secret 2: proof-social-ai-meta-app-secret
- **Nome:** `proof-social-ai-meta-app-secret`
- **Valor:** `40a3ed6ead74584405a2fc7163b17652`
- **Replicação:** Automatic

## 🔧 Opção 2: Via gcloud CLI

Execute os seguintes comandos (requer permissões de Owner/Editor no projeto):

```bash
# Configurar projeto
gcloud config set project proof-social-ai

# Habilitar Secret Manager API (se necessário)
gcloud services enable secretmanager.googleapis.com --project=proof-social-ai

# Criar secret para App ID
echo -n "4109658012632973" | gcloud secrets create proof-social-ai-meta-app-id \
  --data-file=- \
  --replication-policy="automatic" \
  --project=proof-social-ai

# Criar secret para App Secret
echo -n "40a3ed6ead74584405a2fc7163b17652" | gcloud secrets create proof-social-ai-meta-app-secret \
  --data-file=- \
  --replication-policy="automatic" \
  --project=proof-social-ai
```

## ✅ Verificar Secrets Criados

```bash
gcloud secrets list --project=proof-social-ai
```

Você deve ver:
- `proof-social-ai-meta-app-id`
- `proof-social-ai-meta-app-secret`

## 🔐 Permissões Necessárias

Para criar secrets, você precisa de uma das seguintes roles:
- `roles/secretmanager.admin`
- `roles/owner`
- `roles/editor` (com permissão para habilitar APIs)

## 📝 Notas

- Os secrets são criados com replicação automática (disponível em todas as regiões)
- Após criar, os secrets estarão disponíveis para uso pela aplicação
- Certifique-se de que o projeto `proof-social-ai` existe e você tem acesso

