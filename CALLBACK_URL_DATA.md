# 📋 Dados na URL de Callback

## 🔄 Mudança Implementada

O endpoint `/auth/instagram/process-callback` agora **redireciona** para a URL de callback com todos os dados incluídos na query string, ao invés de retornar JSON.

## 📍 Formato da URL de Callback

Após processar o callback, o backend redireciona para:

```
{redirect_uri}?data={JSON_ENCODED_DATA}
```

### Exemplo de URL:

```
https://seu-dominio.com/auth/instagram/callback?data=%7B%22api_key%22%3A%22123e4567-e89b-12d3-a456-426614174000%22%2C%22instagram_accounts%22%3A%5B%7B%22id%22%3A%2217841405309211844%22%2C%22username%22%3A%22minha_conta%22%2C%22name%22%3A%22Minha%20Conta%22%7D%5D%2C%22pages%22%3A%5B%7B%22id%22%3A%22123456789%22%2C%22name%22%3A%22Minha%20P%C3%A1gina%22%2C%22instagram_business_account%22%3A%7B%22id%22%3A%2217841405309211844%22%2C%22username%22%3A%22minha_conta%22%2C%22name%22%3A%22Minha%20Conta%22%7D%7D%5D%2C%22message%22%3A%22Integra%C3%A7%C3%A3o%20Instagram%20configurada%20com%20sucesso%22%2C%22status%22%3A%22success%22%7D
```

## 📦 Estrutura dos Dados

Os dados são enviados como JSON codificado na query string. Após decodificar, você terá:

```json
{
  "api_key": "123e4567-e89b-12d3-a456-426614174000",
  "instagram_accounts": [
    {
      "id": "17841405309211844",
      "username": "minha_conta_instagram",
      "name": "Minha Conta Instagram"
    }
  ],
  "pages": [
    {
      "id": "123456789",
      "name": "Minha Página Facebook",
      "instagram_business_account": {
        "id": "17841405309211844",
        "username": "minha_conta_instagram",
        "name": "Minha Conta Instagram"
      }
    }
  ],
  "message": "Integração Instagram configurada com sucesso",
  "status": "success"
}
```

## 💻 Como Capturar no Frontend

### JavaScript/TypeScript

```javascript
// Quando o Meta redireciona para sua URL de callback
// A API processa e redireciona novamente com os dados

// Capturar dados da URL
const urlParams = new URLSearchParams(window.location.search);
const dataParam = urlParams.get('data');

if (dataParam) {
  // Decodificar JSON
  const data = JSON.parse(decodeURIComponent(dataParam));
  
  // Usar os dados
  console.log('API Key:', data.api_key);
  console.log('Instagram Accounts:', data.instagram_accounts);
  console.log('Pages:', data.pages);
  console.log('Status:', data.status);
  console.log('Message:', data.message);
  
  // Salvar no estado da aplicação
  setIntegrationData(data);
}
```

### React Example

```jsx
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

function InstagramCallback() {
  const [searchParams] = useSearchParams();
  const [integrationData, setIntegrationData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const dataParam = searchParams.get('data');
    
    if (dataParam) {
      try {
        const data = JSON.parse(decodeURIComponent(dataParam));
        setIntegrationData(data);
      } catch (err) {
        setError('Erro ao processar dados do callback');
        console.error(err);
      }
    } else {
      setError('Dados não encontrados na URL');
    }
  }, [searchParams]);

  if (error) {
    return <div>Erro: {error}</div>;
  }

  if (!integrationData) {
    return <div>Carregando...</div>;
  }

  return (
    <div>
      <h2>Integração Configurada!</h2>
      <p>{integrationData.message}</p>
      <p>API Key: {integrationData.api_key}</p>
      <h3>Contas Instagram:</h3>
      <ul>
        {integrationData.instagram_accounts.map(account => (
          <li key={account.id}>
            {account.username} ({account.name})
          </li>
        ))}
      </ul>
      <h3>Páginas:</h3>
      <ul>
        {integrationData.pages.map(page => (
          <li key={page.id}>
            {page.name}
            {page.instagram_business_account && (
              <span> - Instagram: @{page.instagram_business_account.username}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### Next.js Example

```tsx
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

export default function InstagramCallback() {
  const router = useRouter();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (router.isReady) {
      const dataParam = router.query.data as string;
      
      if (dataParam) {
        try {
          const decoded = JSON.parse(decodeURIComponent(dataParam));
          setData(decoded);
        } catch (err) {
          console.error('Erro ao decodificar dados:', err);
        }
      }
    }
  }, [router.isReady, router.query]);

  if (!data) {
    return <div>Carregando...</div>;
  }

  return (
    <div>
      <h1>Integração Configurada!</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
```

## 🔄 Fluxo Completo Atualizado

1. **Frontend** → `POST /auth/instagram/login` com `redirect_uri`
2. **Backend** → Retorna `auth_url` (URL do Meta)
3. **Frontend** → Redireciona usuário para `auth_url`
4. **Usuário** → Autoriza no Meta
5. **Meta** → Redireciona para `redirect_uri?code=XXX&state=YYY`
6. **Frontend** → Chama `POST /auth/instagram/process-callback` com `code`, `state` e `redirect_uri`
7. **Backend** → Processa, salva dados e **redireciona** para `redirect_uri?data={JSON}`
8. **Frontend** → Captura `data` da URL e usa os dados

## ⚠️ Importante

- O endpoint agora retorna um **redirect HTTP 302** ao invés de JSON
- Os dados estão na query string como `data={JSON_ENCODED}`
- Você precisa decodificar a URL e fazer parse do JSON
- O frontend deve estar preparado para receber redirects

## 🧪 Testando

Para testar localmente, você pode usar:

```javascript
// Simular callback
const testData = {
  api_key: "test-uuid",
  instagram_accounts: [{ id: "123", username: "test" }],
  pages: [],
  message: "Test",
  status: "success"
};

const testUrl = `http://localhost:3000/callback?data=${encodeURIComponent(JSON.stringify(testData))}`;
console.log(testUrl);
```

