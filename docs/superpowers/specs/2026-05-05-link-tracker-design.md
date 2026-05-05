# Link Tracker — Design Spec
**Data:** 2026-05-05

## Objetivo

Substituir links afiliados diretos nas mensagens WhatsApp por URLs branded com tracking de cliques. Ex: `https://meubot.up.railway.app/r/iphone-15-pro-amazon` → redireciona para `https://amzn.to/4eo2l4G`.

## Arquitetura

Tudo dentro do projeto existente (Flask + SQLite + Railway). Zero infra nova.

## Banco de Dados

Duas tabelas novas em `db.py`:

```sql
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    url_destino TEXT NOT NULL,
    produto TEXT,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS link_cliques (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL,
    clicado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_slug ON links(slug);
CREATE INDEX IF NOT EXISTS idx_cliques_slug ON link_cliques(slug);
CREATE INDEX IF NOT EXISTS idx_cliques_data ON link_cliques(clicado_em);
```

**Funções novas em `db.py`:**
- `criar_ou_buscar_link(slug, url_destino, produto) -> str` — insere se não existe, retorna slug
- `registrar_clique(slug)` — insere em `link_cliques` com datetime atual
- `buscar_url_destino(slug) -> str | None` — retorna url_destino ou None
- `listar_links_com_stats() -> list[dict]` — retorna links com `total_cliques` e `hora_pico` (hora com mais cliques nas últimas 24h)

## Geração de Slug

Em `bot.py`, função `gerar_slug(produto, loja)`:

```python
import re, unicodedata

def gerar_slug(produto: str, loja: str) -> str:
    texto = f"{produto}-{loja}".lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:60]  # max 60 chars
```

Slug reutilizado se produto já foi enviado antes (mesmo link = mesmo slug).

## Variável de Ambiente

`BASE_URL` — URL pública do Railway (ex: `https://meubot.up.railway.app`). Sem trailing slash. Fallback: `http://localhost:5000`.

## Rotas Flask (`painel/app.py`)

### `/r/<slug>` — público, sem login

```python
@app.route("/r/<slug>")
def redirect_link(slug):
    url = buscar_url_destino(slug)
    if not url:
        return "Link não encontrado", 404
    registrar_clique(slug)
    return redirect(url, code=302)
```

### `/api/links` — protegido com `@login_required`

Retorna JSON com lista de links + stats:

```json
[
  {
    "slug": "iphone-15-pro-amazon",
    "produto": "iPhone 15 Pro 256GB",
    "url_destino": "https://amzn.to/4eo2l4G",
    "criado_em": "2026-05-05T08:00:00",
    "total_cliques": 47,
    "hora_pico": "18h-19h"
  }
]
```

`hora_pico`: hora (0-23) com mais cliques nas últimas 24h. Null se sem cliques.

## Integração em `bot.py`

Em `montar_mensagem(oferta)`, antes de montar o texto:

```python
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
slug = gerar_slug(oferta["produto"], oferta["loja"])
criar_ou_buscar_link(slug, oferta["link_afiliado"], oferta["produto"])
link_rastreado = f"{BASE_URL}/r/{slug}"
```

Usa `link_rastreado` no lugar de `oferta['link_afiliado']` na mensagem.

## Painel (dashboard)

Nova aba "Links" em `index.html`. Tabela com colunas:
- Produto
- Slug
- Cliques (total)
- Hora de pico
- Criado em

Polling a cada 30s via `/api/links` (mesmo padrão das outras seções).

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `db.py` | +2 tabelas, +4 funções |
| `bot.py` | +`gerar_slug()`, modifica `montar_mensagem()` |
| `painel/app.py` | +2 rotas (`/r/<slug>`, `/api/links`) |
| `painel/templates/index.html` | +aba Links |
| `config.env.example` | +`BASE_URL` |

## Fora do Escopo

- Expiração de links
- Geolocalização de cliques
- Gráfico visual (só texto com hora de pico)
- Edição/deleção de links pelo painel
