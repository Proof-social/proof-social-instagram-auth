# 🔄 Mudanças Necessárias no Frontend

## ✅ Mudança Implementada no Backend

O backend agora retorna **JSON** ao invés de HTTP 302 redirect. Isso resolve o problema de CORS e permite que o frontend controle o redirect.

## 📝 O que Mudou

### Antes (HTTP 302):
- Backend retornava HTTP 302 redirect
- Navegador tentava seguir redirect automaticamente
- Causava erro 405 (Method Not Allowed)

### Agora (JSON):
- Backend retorna JSON com `redirect_url` e todos os dados
- Frontend recebe os dados e faz redirect manualmente
- Funciona perfeitamente com `fetch()`

## 🔧 Mudanças Necessárias no Frontend

### 1. Atualizar o tratamento da resposta

**ANTES:**
```typescript
const response = await fetch(apiUrl, {
  method: 'POST',
  // ...
});

// Esperava redirect automático (não funcionava)
if (response.status === 302 || response.redirected) {
  // Não chegava aqui
}
```

**AGORA:**
```typescript
const response = await fetch(apiUrl, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    code: code,
    state: state,
    redirect_uri: `${window.location.origin}${window.location.pathname}`
  })
});

if (!response.ok) {
  const errorData = await response.json();
  throw new Error(`Erro ${response.status}: ${JSON.stringify(errorData)}`);
}

// ✅ Receber JSON com os dados
const data = await response.json();

// ✅ Fazer redirect manualmente
if (data.redirect_url) {
  window.location.href = data.redirect_url;
} else {
  // Ou usar os dados diretamente
  await saveIntegrationData(data);
}
```

### 2. Estrutura da Resposta

A resposta agora vem assim:

```json
{
  "redirect_url": "https://seu-dominio.com/auth/instagram/callback?data={JSON_ENCODED}",
  "api_key": "123e4567-e89b-12d3-a456-426614174000",
  "instagram_accounts": [
    {
      "id": "17841405309211844",
      "username": "minha_conta",
      "name": "Minha Conta"
    }
  ],
  "pages": [
    {
      "id": "123456789",
      "name": "Minha Página",
      "instagram_business_account": {
        "id": "17841405309211844",
        "username": "minha_conta",
        "name": "Minha Conta"
      }
    }
  ],
  "message": "Integração Instagram configurada com sucesso",
  "status": "success"
}
```

### 3. Opções de Implementação

#### Opção A: Usar redirect_url (recomendado)

```typescript
const data = await response.json();

// Fazer redirect para a URL com dados na query string
if (data.redirect_url) {
  window.location.href = data.redirect_url;
  // A página será recarregada com ?data={JSON} na URL
  // O useEffect detectará e processará os dados
}
```

#### Opção B: Usar dados diretamente (mais simples)

```typescript
const data = await response.json();

// Usar os dados diretamente, sem redirect
await saveIntegrationData({
  api_key: data.api_key,
  instagram_accounts: data.instagram_accounts,
  pages: data.pages
});

// Redirecionar para página de sucesso
router.push('/dashboard?integration=success');
```

## 📋 Código Completo Atualizado

```typescript
// InstagramCallbackPage.tsx
useEffect(() => {
  async function handleCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    
    // ✅ PRIMEIRO: Verificar se já temos dados (após redirect)
    const dataParam = urlParams.get('data');
    
    if (dataParam) {
      try {
        const data = JSON.parse(decodeURIComponent(dataParam));
        console.log('✅ Dados recebidos:', data);
        
        await saveIntegrationData(data);
        
        // Limpar URL
        window.history.replaceState({}, '', '/dashboard');
        router.push('/dashboard?integration=success');
      } catch (error) {
        console.error('Erro ao processar dados:', error);
      }
      return;
    }

    // ✅ SEGUNDO: Verificar se temos code (primeiro callback do Meta)
    const code = urlParams.get('code');
    const state = urlParams.get('state');

    if (!code || !state) {
      console.error('❌ Code ou state não encontrado');
      return;
    }

    // Proteção: verificar se já processamos
    const processedKey = `ig_callback_${code}`;
    if (sessionStorage.getItem(processedKey)) {
      console.log('⚠️ Code já processado');
      return;
    }
    sessionStorage.setItem(processedKey, 'true');

    try {
      const firebaseToken = await getFirebaseToken();
      
      console.log('📡 Chamando backend para processar callback...');

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
            redirect_uri: `${window.location.origin}${window.location.pathname}`
          })
        }
      );

      // ✅ Verificar se resposta é OK
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Erro ${response.status}: ${JSON.stringify(errorData)}`);
      }

      // ✅ Receber JSON com os dados
      const data = await response.json();
      console.log('✅ Resposta do backend:', data);

      // ✅ Opção A: Fazer redirect para URL com dados
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
        return;
      }

      // ✅ Opção B: Usar dados diretamente
      await saveIntegrationData(data);
      router.push('/dashboard?integration=success');

    } catch (error) {
      console.error('❌ Erro ao processar callback:', error);
      sessionStorage.removeItem(processedKey);
    }
  }

  handleCallback();
}, []);
```

## ✅ Checklist de Mudanças

- [ ] Remover verificação de `response.status === 302`
- [ ] Adicionar verificação de `response.ok`
- [ ] Fazer `await response.json()` para receber os dados
- [ ] Usar `data.redirect_url` para fazer redirect manual
- [ ] Ou usar `data` diretamente se preferir
- [ ] Manter proteção com sessionStorage
- [ ] Manter verificação de `data` na URL primeiro

## 🎯 Resumo

**Mudança principal:** O backend agora retorna JSON ao invés de HTTP 302. O frontend precisa:
1. Fazer `await response.json()` para receber os dados
2. Usar `data.redirect_url` para fazer redirect manual com `window.location.href`
3. Ou usar os dados diretamente sem redirect

Isso resolve o problema de CORS e status 0!

