# Habilitar APIs do Google Cloud - Projeto proof-social

## 📋 APIs Necessárias

O projeto `proof-social-instagram-auth` requer as seguintes APIs do Google Cloud:

1. **Secret Manager API** (`secretmanager.googleapis.com`)
   - Para armazenar App ID e App Secret do Meta
   - Para armazenar tokens de acesso dos usuários

2. **Firestore API** (`firestore.googleapis.com`)
   - Para salvar dados de integrações Instagram
   - Para armazenar API keys e informações de contas

3. **Cloud Run API** (`run.googleapis.com`)
   - Para fazer deploy da aplicação FastAPI
   - Para executar o serviço em produção

4. **Cloud Build API** (`cloudbuild.googleapis.com`)
   - Para build de containers Docker
   - Para automatizar o processo de deploy

5. **Container Registry API** (`containerregistry.googleapis.com`)
   - Para armazenar imagens Docker
   - Alternativa: Artifact Registry

6. **Artifact Registry API** (`artifactregistry.googleapis.com`)
   - Alternativa moderna ao Container Registry
   - Para armazenar imagens Docker

## 🔧 Opção 1: Via Script (Recomendado)

Execute o script com uma conta que tenha permissões de Owner/Editor:

```bash
cd /Users/luizsegundo/proof-social-instagram-auth
chmod +x enable_apis.sh
./enable_apis.sh
```

## 🔧 Opção 2: Via gcloud CLI

Execute os seguintes comandos:

```bash
gcloud config set project proof-social

# Habilitar todas as APIs de uma vez
gcloud services enable \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    --project=proof-social
```

## 🔧 Opção 3: Via Console do Google Cloud

### Habilitar todas as APIs de uma vez:

1. Acesse: https://console.cloud.google.com/apis/library?project=proof-social
2. Para cada API, clique no nome e depois em "ENABLE":

   - **Secret Manager API**
     - Link: https://console.cloud.google.com/apis/library/secretmanager.googleapis.com?project=proof-social
   
   - **Cloud Firestore API**
     - Link: https://console.cloud.google.com/apis/library/firestore.googleapis.com?project=proof-social
   
   - **Cloud Run API**
     - Link: https://console.cloud.google.com/apis/library/run.googleapis.com?project=proof-social
   
   - **Cloud Build API**
     - Link: https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=proof-social
   
   - **Container Registry API**
     - Link: https://console.cloud.google.com/apis/library/containerregistry.googleapis.com?project=proof-social
   
   - **Artifact Registry API**
     - Link: https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com?project=proof-social

### Ou habilitar todas de uma vez:

Acesse este link para ver todas as APIs e habilitar as necessárias:
https://console.cloud.google.com/apis/library?project=proof-social&q=secretmanager%20OR%20firestore%20OR%20run%20OR%20cloudbuild%20OR%20containerregistry%20OR%20artifactregistry

## ✅ Verificar APIs Habilitadas

Após habilitar, verifique com:

```bash
gcloud services list --enabled --project=proof-social \
    --filter="name:secretmanager OR name:firestore OR name:run OR name:cloudbuild OR name:containerregistry OR name:artifactregistry"
```

## 🔐 Permissões Necessárias

Para habilitar APIs, você precisa de uma das seguintes roles:
- `roles/owner`
- `roles/editor`
- `roles/serviceusage.serviceUsageAdmin`

## ⚠️ Nota Importante

- As APIs podem levar alguns minutos para serem totalmente habilitadas
- Algumas APIs podem ter custos associados (verifique a documentação)
- Certifique-se de que o projeto `proof-social` existe e você tem acesso

