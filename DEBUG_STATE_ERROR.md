# 🐛 Debug: Erro "State não corresponde ao usuário autenticado"

## ❌ Erro Observado

```
{detail: 'State não corresponde ao usuário autenticado'}
```

## 🔍 Causas Possíveis

### 1. Token Firebase Expirado Entre Chamadas

**Problema:** O token Firebase pode expirar entre a chamada de `/auth/instagram/login` e `/auth/instagram/process-callback`.

**Solução:** O frontend deve obter um novo token Firebase antes de cada chamada:

```typescript
// ❌ ERRADO: Usar token antigo
const oldToken = localStorage.getItem('firebase_token');
await fetch('/auth/instagram/process-callback', {
  headers: { 'Authorization': `Bearer ${oldToken}` }
});

// ✅ CORRETO: Obter token fresco
const auth = getAuth();
const user = auth.currentUser;
const freshToken = await user.getIdToken(); // Sempre obtém token atualizado
await fetch('/auth/instagram/process-callback', {
  headers: { 'Authorization': `Bearer ${freshToken}` }
});
```

### 2. State Modificado pelo Meta ou URL Encoding

**Problema:** O Meta pode modificar o `state` na URL, ou pode haver problemas com encoding/decoding.

**Solução:** O frontend deve extrair o `state` exatamente como veio da URL:

```typescript
// ✅ CORRETO: Extrair state da URL sem modificações
const urlParams = new URLSearchParams(window.location.search);
const state = urlParams.get('state'); // Não fazer trim() ou outras modificações

// Enviar state exatamente como recebido
await fetch('/auth/instagram/process-callback', {
  body: JSON.stringify({
    code: urlParams.get('code'),
    state: state, // State exatamente como veio da URL
    redirect_uri: window.location.origin + window.location.pathname
  })
});
```

### 3. User UID Diferente Entre Chamadas

**Problema:** O usuário pode ter feito logout/login entre as chamadas, resultando em um `user_uid` diferente.

**Solução:** Verificar se o usuário ainda está autenticado:

```typescript
const auth = getAuth();
const user = auth.currentUser;

if (!user) {
  // Usuário não está mais autenticado
  // Redirecionar para login
  router.push('/login');
  return;
}

// Obter token do usuário atual
const token = await user.getIdToken();
```

### 4. Múltiplas Chamadas Simultâneas

**Problema:** O frontend pode estar fazendo múltiplas chamadas ao mesmo tempo, causando race conditions.

**Solução:** Adicionar proteção contra chamadas duplicadas:

```typescript
let isProcessing = false;

async function processCallback() {
  if (isProcessing) {
    console.log('Já está processando...');
    return;
  }
  
  isProcessing = true;
  
  try {
    // Processar callback
    await fetch('/auth/instagram/process-callback', { ... });
  } finally {
    isProcessing = false;
  }
}
```

## 🔧 Logs Adicionados

Adicionei logs detalhados no backend para ajudar no debug:

### No endpoint `/auth/instagram/login`:
- Log do `user_uid` usado como `state`
- Log do `state` que será enviado na URL

### No endpoint `/auth/instagram/process-callback`:
- Log do `state` recebido (com tipo, tamanho, repr)
- Log do `user_uid` extraído do token (com tipo, tamanho, repr)
- Comparação detalhada entre os dois valores

## 📋 Checklist de Verificação

Verifique no frontend:

- [ ] Token Firebase é obtido **fresco** antes de cada chamada (`getIdToken()`)
- [ ] `state` é extraído da URL **sem modificações** (sem trim, sem decode extra)
- [ ] Usuário ainda está autenticado quando processa o callback
- [ ] Não há múltiplas chamadas simultâneas ao mesmo endpoint
- [ ] `redirect_uri` é **exatamente igual** nas duas chamadas (login e callback)

## 🔍 Como Verificar nos Logs

Após fazer uma tentativa de conexão, verifique os logs do Cloud Run:

1. Procure por `🔐 Gerando URL de autorização:` - mostra o `state` que foi gerado
2. Procure por `🔍 Validação de State:` - mostra a comparação entre `state` recebido e `user_uid`
3. Procure por `✅ Token Firebase validado` - mostra o `user_uid` extraído do token

Exemplo de log esperado:

```
INFO: 🔐 Gerando URL de autorização:
INFO:   - User UID: 'abc123xyz' (tipo: <class 'str'>, len: 9)
INFO:   - State que será usado: 'abc123xyz' (tipo: <class 'str'>, len: 9)
INFO: ✅ URL de autorização gerada para user_uid: abc123xyz

INFO: ✅ Token Firebase validado para user_uid: abc123xyz (tipo: <class 'str'>, len: 9)
INFO: 🔍 Validação de State:
INFO:   - State recebido: 'abc123xyz' (tipo: <class 'str'>, len: 9)
INFO:   - User UID do token: 'abc123xyz' (tipo: <class 'str'>, len: 9)
INFO:   - São iguais? True
INFO: ✅ State validado com sucesso!
```

Se os valores forem diferentes, você verá:

```
INFO: 🔍 Validação de State:
INFO:   - State recebido: 'abc123xyz' (tipo: <class 'str'>, len: 9)
INFO:   - User UID do token: 'def456uvw' (tipo: <class 'str'>, len: 9)
INFO:   - São iguais? False
ERROR: ❌ State não corresponde! State: 'abc123xyz' != User UID: 'def456uvw'
```

## 🛠️ Solução Temporária (Apenas para Debug)

Se precisar de uma solução temporária para testar, você pode comentar a validação do state (NÃO RECOMENDADO PARA PRODUÇÃO):

```python
# TEMPORÁRIO: Comentar validação para debug
# if request.state != user_uid:
#     raise HTTPException(...)

logger.warning(f"⚠️ VALIDAÇÃO DE STATE DESABILITADA (APENAS DEBUG)")
```

**⚠️ IMPORTANTE:** Isso remove a proteção contra CSRF. Use apenas para debug e remova antes de ir para produção.

## 📞 Próximos Passos

1. Verifique os logs do Cloud Run após uma tentativa de conexão
2. Compare os valores de `state` e `user_uid` nos logs
3. Verifique se o frontend está obtendo token fresco antes de cada chamada
4. Verifique se o `state` não está sendo modificado no frontend

