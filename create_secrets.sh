#!/bin/bash

# Script para criar secrets no Google Cloud Secret Manager
# Execute este script após habilitar a Secret Manager API no projeto proof-social

PROJECT_ID="proof-social"
APP_ID="4109658012632973"
APP_SECRET="40a3ed6ead74584405a2fc7163b17652"

echo "🔐 Criando secrets no projeto $PROJECT_ID..."

# Configurar projeto
gcloud config set project $PROJECT_ID

# Habilitar Secret Manager API (se necessário)
echo "📦 Habilitando Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

# Criar secret para App ID
echo "📝 Criando secret: proof-social-meta-app-id"
echo -n "$APP_ID" | gcloud secrets create proof-social-meta-app-id \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# Criar secret para App Secret
echo "📝 Criando secret: proof-social-meta-app-secret"
echo -n "$APP_SECRET" | gcloud secrets create proof-social-meta-app-secret \
  --data-file=- \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

echo "✅ Secrets criados com sucesso!"
echo ""
echo "Verificar secrets:"
echo "  gcloud secrets list --project=$PROJECT_ID"

