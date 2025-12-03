#!/bin/bash

# Script para inicializar o repositório Git e conectar ao GitHub

echo "🚀 Configurando repositório proof-social-instagram-auth..."

# Inicializar Git
git init

# Adicionar todos os arquivos
git add .

# Commit inicial
git commit -m "Initial commit: Proof Social Instagram OAuth API"

# Adicionar remote do GitHub (organização proof-social)
git remote add origin https://github.com/proof-social/proof-social-instagram-auth.git

echo "✅ Repositório configurado!"
echo ""
echo "📝 Próximos passos:"
echo "1. Crie o repositório 'proof-social-instagram-auth' na organização 'proof-social' no GitHub"
echo "2. Execute: git push -u origin main"
echo ""
echo "Ou se preferir usar master:"
echo "   git branch -M master"
echo "   git push -u origin master"

