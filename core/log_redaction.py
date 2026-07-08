"""Redação de segredos em logs.

Motivação: o logger INFO do httpx registra a URL completa de cada request,
incluindo query params. As chamadas GET a graph.instagram.com/access_token e
/v20.0/me (routes/auth.py) carregam `client_secret` e `access_token` na query
string — isso vazava o secret do app Meta e tokens IGAA... em texto puro no
Cloud Logging.

Estratégia (defesa em profundidade, combinada com silenciar o httpx em main.py):
- Filtro instalado nos handlers do root logger que rediga QUALQUER record antes
  de formatar/emitir. Cobre o request-line do httpx e também qualquer logger
  próprio que, por engano, formate uma URL/token completo.
- Redige tanto query params sensíveis (`client_secret=...`, `access_token=...`)
  quanto tokens Meta/Instagram reconhecíveis pelo prefixo (IGAA.../EAA...),
  truncando para os 8 primeiros chars.
"""

from __future__ import annotations

import logging
import re

# Chaves de query string / form cujo valor nunca pode chegar aos logs.
_SENSITIVE_KEYS = ("client_secret", "access_token")

# Casa `chave=valor` numa query string, parando no próximo delimitador
# (& espaço aspas ou fechamento de dict).
_QS_PATTERN = re.compile(
    r"(?i)\b(" + "|".join(_SENSITIVE_KEYS) + r")=([^&\s\"'}\)]+)"
)

# Tokens de acesso Meta/Instagram: prefixo IGAA (Instagram Login API) ou EAA
# (Facebook Graph), seguidos de string longa. Pega tokens mesmo fora de uma
# query string (ex.: se aparecerem soltos numa mensagem de erro).
_TOKEN_PATTERN = re.compile(r"\b((?:IGAA|EAA)[A-Za-z0-9_\-]{6,})")


def _mask(value: str) -> str:
    """Trunca para os 8 primeiros chars — o bastante para correlacionar em
    debug sem expor o segredo."""
    if len(value) > 8:
        return value[:8] + "…REDACTED"
    return "…REDACTED"


def redact(text: str) -> str:
    text = _QS_PATTERN.sub(lambda m: f"{m.group(1)}={_mask(m.group(2))}", text)
    text = _TOKEN_PATTERN.sub(lambda m: _mask(m.group(1)), text)
    return text


class RedactSecretsFilter(logging.Filter):
    """Rediga secrets/tokens no texto final do log record.

    Instalar nos HANDLERS (não no logger) para capturar também os records que
    propagam de loggers-filho como o `httpx`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            # Se a própria formatação falhar, deixa passar sem mexer.
            return True
        redacted = redact(msg)
        if redacted != msg:
            # Substitui a mensagem já renderizada e zera args para não
            # reformatar (o que reintroduziria o segredo).
            record.msg = redacted
            record.args = ()
        return True


def install_log_redaction() -> None:
    """Instala o filtro em todos os handlers do root logger e silencia o log
    de request do httpx (que emitia a URL completa em nível INFO)."""
    redact_filter = RedactSecretsFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        # Evita duplicar em reload/reimport.
        if not any(isinstance(f, RedactSecretsFilter) for f in handler.filters):
            handler.addFilter(redact_filter)

    # Silencia o request-line do httpx (INFO): elimina o vazamento na fonte.
    # WARNING+ ainda passa, mas esses records também são redigidos pelo filtro.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
