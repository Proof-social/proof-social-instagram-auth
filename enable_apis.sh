#!/bin/bash

# Script para habilitar todas as APIs necessárias no projeto proof-social
# Execute este script com uma conta que tenha permissões de Owner/Editor

PROJECT_ID="proof-social"

echo "🔧 Habilitando APIs necessárias no projeto $PROJECT_ID..."
echo ""

# Configurar projeto
gcloud config set project $PROJECT_ID

# APIs necessárias para o projeto
APIS=(
    "secretmanager.googleapis.com"      # Secret Manager - para armazenar secrets
    "firestore.googleapis.com"           # Firestore - para salvar integrações
    "run.googleapis.com"                 # Cloud Run - para deploy da aplicação
    "cloudbuild.googleapis.com"         # Cloud Build - para build de containers
    "containerregistry.googleapis.com"  # Container Registry - para armazenar imagens
    "artifactregistry.googleapis.com"   # Artifact Registry - alternativa ao Container Registry
)

echo "📦 Habilitando as seguintes APIs:"
for api in "${APIS[@]}"; do
    echo "   - $api"
done
echo ""

# Habilitar cada API
for api in "${APIS[@]}"; do
    echo "🔄 Habilitando $api..."
    gcloud services enable $api --project=$PROJECT_ID
    if [ $? -eq 0 ]; then
        echo "   ✅ $api habilitada com sucesso"
    else
        echo "   ❌ Erro ao habilitar $api"
    fi
    echo ""
done

echo "✅ Processo concluído!"
echo ""
echo "📋 Verificar APIs habilitadas:"
echo "   gcloud services list --enabled --project=$PROJECT_ID"

