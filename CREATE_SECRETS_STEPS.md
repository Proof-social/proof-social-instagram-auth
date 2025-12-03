# Passo a Passo: Criar Secrets no Google Cloud Secret Manager

## 📋 Informações dos Secrets

- **Secret 1:**
  - Nome: `proof-social-ai-meta-app-id`
  - Valor: `4109658012632973`

- **Secret 2:**
  - Nome: `proof-social-ai-meta-app-secret`
  - Valor: `40a3ed6ead74584405a2fc7163b17652`

## 🔧 Passo a Passo no Console

### 1. Acessar o Secret Manager
Acesse: https://console.cloud.google.com/security/secret-manager?project=proof-social-ai

### 2. Criar o Primeiro Secret (App ID)

1. Clique no botão **"CREATE SECRET"** (ou "CRIAR SECRET")
2. Preencha os campos:
   - **Name** (Nome): `proof-social-ai-meta-app-id`
   - **Secret value** (Valor do secret): `4109658012632973`
   - **Replication** (Replicação): Selecione **"Automatic"** (Automático)
3. Clique em **"CREATE SECRET"** (ou "CRIAR SECRET")

### 3. Criar o Segundo Secret (App Secret)

1. Clique novamente em **"CREATE SECRET"**
2. Preencha os campos:
   - **Name** (Nome): `proof-social-ai-meta-app-secret`
   - **Secret value** (Valor do secret): `40a3ed6ead74584405a2fc7163b17652`
   - **Replication** (Replicação): Selecione **"Automatic"** (Automático)
3. Clique em **"CREATE SECRET"** (ou "CRIAR SECRET")

### 4. Verificar

Após criar ambos os secrets, você deve ver na lista:
- ✅ `proof-social-ai-meta-app-id`
- ✅ `proof-social-ai-meta-app-secret`

## ✅ Comandos para Verificar (se tiver permissão)

```bash
gcloud secrets list --project=proof-social-ai --filter="name~proof-social-ai-meta"
```

## 🔐 Permissões Necessárias

Para criar secrets, você precisa de uma das seguintes roles:
- `roles/secretmanager.admin`
- `roles/owner`
- `roles/editor`

## 📝 Notas

- Os secrets são criados com replicação automática (disponível em todas as regiões)
- Após criar, os secrets estarão disponíveis para uso pela aplicação
- Certifique-se de que está logado com uma conta que tem permissões no projeto `proof-social-ai`

