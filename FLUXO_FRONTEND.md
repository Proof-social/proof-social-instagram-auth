# 🔄 Fluxo OAuth Instagram - Guia para Frontend

## ⚠️ IMPORTANTE: Entendendo o Fluxo Correto

**O Meta SEMPRE redireciona para o FRONTEND, nunca para o backend diretamente.**

O backend é uma API que o frontend chama via HTTP POST. O Meta não chama o backend diretamente.

---

## 🔄 Fluxo Correto (Passo a Passo)

### **Passo 1: Frontend inicia OAuth**

Frontend chama a API para obter a URL de autorização:

```javascript
const response = await fetch(
  'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/login',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      redirect_uri: 'https://seu-dominio.com/auth/instagram/callback'  // URL do FRONTEND
    })
  }
);

const { auth_url } = await response.json();
// auth_url = "https://www.facebook.com/v20.0/dialog/oauth?...&redirect_uri=https://seu-dominio.com/auth/instagram/callback&..."
```

### **Passo 2: Frontend redireciona usuário para Meta**

```javascript
window.location.href = auth_url;
```

O usuário vê a tela de autorização do Meta.

### **Passo 3: Usuário autoriza no Meta**

Usuário clica em "Continuar" ou "Autorizar" na tela do Meta.

### **Passo 4: Meta redireciona para o FRONTEND**

**⚠️ IMPORTANTE: O Meta redireciona para a URL do FRONTEND, não para o backend!**

```
https://seu-dominio.com/auth/instagram/callback?code=ABC123&state=user123
```

O Meta redireciona para a URL que você passou em `redirect_uri` (que é a URL do seu frontend).

### **Passo 5: Frontend recebe callback e chama a API**

O frontend recebe o callback na URL e então chama a API do backend:

```javascript
// Na página de callback do frontend
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// Frontend chama a API do backend
const response = await fetch(
  'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      code: code,
      state: state,
      redirect_uri: 'https://seu-dominio.com/auth/instagram/callback'  // Mesma URL do passo 1
    })
  }
);

// A API retorna um REDIRECT HTTP 302
// O navegador segue automaticamente o redirect
```

### **Passo 6: Backend processa e redireciona de volta para o FRONTEND**

A API processa tudo (troca code por token, salva no Firestore, etc.) e retorna um **HTTP 302 Redirect** para:

```
https://seu-dominio.com/auth/instagram/callback?data={JSON_ENCODED}
```

O navegador segue automaticamente esse redirect.

### **Passo 7: Frontend captura dados da URL**

O frontend agora está na mesma URL de callback, mas agora com `data` na query string:

```javascript
// Na mesma página de callback, mas agora com data
const urlParams = new URLSearchParams(window.location.search);
const dataParam = urlParams.get('data');

if (dataParam) {
  // Decodificar JSON
  const data = JSON.parse(decodeURIComponent(dataParam));
  
  // Usar os dados
  console.log('API Key:', data.api_key);
  console.log('Instagram Accounts:', data.instagram_accounts);
  console.log('Pages:', data.pages);
  
  // Salvar no Firestore ou estado da aplicação
  await saveToFirestore(data);
}
```

---

## 📋 Resumo Visual do Fluxo

```
┌─────────┐                    ┌──────────┐                    ┌─────────┐
│Frontend │                    │ Backend  │                    │  Meta   │
│         │                    │   API    │                    │   API   │
└───┬─────┘                    └────┬─────┘                    └────┬────┘
    │                                │                                │
    │ 1. POST /auth/instagram/login  │                                │
    │    { redirect_uri: "..." }     │                                │
    ├───────────────────────────────>│                                │
    │                                │                                │
    │ 2. Response: { auth_url }      │                                │
    │<───────────────────────────────┤                                │
    │                                │                                │
    │ 3. Redirect to auth_url        │                                │
    │─────────────────────────────────────────────────────────────────>│
    │                                │                                │
    │                                │                                │ 4. User
    │                                │                                │ Authorizes
    │                                │                                │
    │ 5. Meta redirects to FRONTEND │                                │
    │<─────────────────────────────────────────────────────────────────┤
    │    callback?code=XXX&state=YYY │                                │
    │                                │                                │
    │ 6. POST /auth/instagram/       │                                │
    │    process-callback            │                                │
    │    { code, state, redirect_uri }│                                │
    ├───────────────────────────────>│                                │
    │                                │                                │
    │                                │ 7. Exchange code for token     │
    │                                ├───────────────────────────────>│
    │                                │                                │
    │                                │<───────────────────────────────┤
    │                                │                                │
    │                                │ 8. Process & save              │
    │                                │                                │
    │ 9. HTTP 302 Redirect           │                                │
    │    callback?data={JSON}        │                                │
    │<───────────────────────────────┤                                │
    │                                │                                │
    │ 10. Read data from URL         │                                │
    │                                │                                │
```

---

## ✅ Configuração no Meta App

### URL de Callback no Meta

**Configure no Facebook Developers:**

```
https://seu-dominio.com/auth/instagram/callback
```

**⚠️ IMPORTANTE:** Esta é a URL do **FRONTEND**, não do backend!

O Meta redireciona para esta URL com `code` e `state`. O frontend então chama a API do backend.

---

## 🔧 Implementação Completa no Frontend

### Exemplo: React/Next.js

```jsx
// pages/auth/instagram/callback.js ou componente de callback
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function InstagramCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState('processing');

  useEffect(() => {
    async function processCallback() {
      // Verificar se já temos os dados (segundo redirect)
      const dataParam = searchParams.get('data');
      
      if (dataParam) {
        // Já temos os dados, processar
        try {
          const data = JSON.parse(decodeURIComponent(dataParam));
          console.log('Dados recebidos:', data);
          
          // Salvar no Firestore ou estado
          await saveIntegrationData(data);
          
          setStatus('success');
          // Redirecionar para página de sucesso
          router.push('/dashboard?integration=success');
        } catch (error) {
          console.error('Erro ao processar dados:', error);
          setStatus('error');
        }
        return;
      }

      // Primeiro callback do Meta - temos code e state
      const code = searchParams.get('code');
      const state = searchParams.get('state');

      if (!code || !state) {
        setStatus('error');
        return;
      }

      // Obter token Firebase
      const firebaseToken = await getFirebaseToken();

      // Chamar API do backend
      try {
        const response = await fetch(
          'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback',
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${firebaseToken}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              code: code,
              state: state,
              redirect_uri: `${window.location.origin}/auth/instagram/callback`
            })
          }
        );

        // A API retorna HTTP 302, o navegador segue automaticamente
        // Não precisamos fazer nada aqui, o redirect acontece automaticamente
        // O useEffect será chamado novamente com data na URL
        
      } catch (error) {
        console.error('Erro ao processar callback:', error);
        setStatus('error');
      }
    }

    processCallback();
  }, [searchParams, router]);

  if (status === 'processing') {
    return <div>Processando integração...</div>;
  }

  if (status === 'error') {
    return <div>Erro ao processar integração</div>;
  }

  return <div>Sucesso!</div>;
}
```

### Exemplo: JavaScript Vanilla

```javascript
// callback.html
async function handleCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  
  // Verificar se já temos os dados (segundo redirect)
  const dataParam = urlParams.get('data');
  
  if (dataParam) {
    // Processar dados
    const data = JSON.parse(decodeURIComponent(dataParam));
    console.log('Dados recebidos:', data);
    
    // Salvar no Firestore
    await saveToFirestore(data);
    
    // Redirecionar para página de sucesso
    window.location.href = '/dashboard?success=true';
    return;
  }

  // Primeiro callback - temos code e state
  const code = urlParams.get('code');
  const state = urlParams.get('state');

  if (!code || !state) {
    alert('Erro: code ou state não encontrado');
    return;
  }

  // Obter token Firebase
  const firebaseToken = await getFirebaseToken();

  // Chamar API do backend
  const response = await fetch(
    'https://proof-social-instagram-auth-30922479426.us-central1.run.app/auth/instagram/process-callback',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        code: code,
        state: state,
        redirect_uri: window.location.href.split('?')[0] // URL atual sem query params
      })
    }
  );

  // A API retorna HTTP 302, o navegador segue automaticamente
  // Não precisamos fazer nada, o redirect acontece sozinho
}

// Executar quando a página carregar
window.addEventListener('DOMContentLoaded', handleCallback);
```

---

## ❌ Erros Comuns

### ❌ ERRADO: Meta redireciona para o backend
```
Meta → https://api.backend.com/callback?code=XXX
```
**Isso está ERRADO!** O Meta redireciona para o frontend.

### ✅ CORRETO: Meta redireciona para o frontend
```
Meta → https://seu-dominio.com/auth/instagram/callback?code=XXX
Frontend → Chama API do backend
Backend → Redireciona de volta para frontend com dados
```

---

## 📝 Checklist para Frontend

- [ ] URL de callback configurada no Meta aponta para o **frontend**
- [ ] Frontend tem uma rota/página para receber o callback do Meta
- [ ] Frontend extrai `code` e `state` da URL quando Meta redireciona
- [ ] Frontend chama `POST /auth/instagram/process-callback` com code, state e redirect_uri
- [ ] Frontend está preparado para receber redirect HTTP 302 da API
- [ ] Frontend captura `data` da URL após o redirect da API
- [ ] Frontend faz parse do JSON e salva os dados

---

## 🔗 URLs Importantes

- **API Base:** `https://proof-social-instagram-auth-30922479426.us-central1.run.app`
- **Endpoint Login:** `POST /auth/instagram/login`
- **Endpoint Callback:** `POST /auth/instagram/process-callback`
- **Documentação Swagger:** `https://proof-social-instagram-auth-30922479426.us-central1.run.app/docs`

---

## 💡 Dica

O fluxo tem **dois redirects**:
1. **Meta → Frontend** (com `code` e `state`)
2. **Backend → Frontend** (com `data`)

O frontend precisa lidar com ambos na mesma página/rota de callback.

