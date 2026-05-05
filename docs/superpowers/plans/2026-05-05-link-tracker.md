# Link Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct affiliate links in WhatsApp messages with branded tracked URLs (`/r/<slug>`) that count clicks and show peak hour in the dashboard.

**Architecture:** Two new SQLite tables (`links`, `link_cliques`) in the existing `db.py`. Two new Flask routes in `painel/app.py` (`/r/<slug>` public redirect, `/api/links` protected stats). `bot.py` generates slugs and stores them before mounting the message.

**Tech Stack:** Python 3.12, Flask, SQLite (via `sqlite3`), existing Railway deploy.

---

## File Map

| File | Change |
|------|--------|
| `db.py` | +2 tables in `init_db()`, +4 functions |
| `bot.py` | +`gerar_slug()`, modify `montar_mensagem()` |
| `painel/app.py` | +2 routes, add new db imports |
| `painel/templates/index.html` | +Links card with table + polling |
| `config.env.example` | +`BASE_URL` |

---

### Task 1: Add DB tables and functions

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Add tables to `init_db()`**

In `db.py`, inside the `init_db()` function after the existing `con.execute` calls, add:

```python
        con.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                url_destino TEXT NOT NULL,
                produto TEXT,
                criado_em TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS link_cliques (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                clicado_em TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_slug ON links(slug)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cliques_slug ON link_cliques(slug)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_cliques_data ON link_cliques(clicado_em)")
```

- [ ] **Step 2: Add the 4 new functions at the end of `db.py`**

```python
def criar_ou_buscar_link(slug: str, url_destino: str, produto: str) -> str:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO links (slug, url_destino, produto, criado_em) VALUES (?,?,?,?)",
            (slug, url_destino, produto, datetime.now().isoformat()),
        )
        con.commit()
    return slug


def registrar_clique(slug: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO link_cliques (slug, clicado_em) VALUES (?,?)",
            (slug, datetime.now().isoformat()),
        )
        con.commit()


def buscar_url_destino(slug: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT url_destino FROM links WHERE slug = ?", (slug,)
        ).fetchone()
    return row[0] if row else None


def listar_links_com_stats() -> list[dict]:
    limite_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    with _conn() as con:
        links = con.execute(
            "SELECT slug, url_destino, produto, criado_em FROM links ORDER BY criado_em DESC"
        ).fetchall()
        result = []
        for slug, url_destino, produto, criado_em in links:
            total = con.execute(
                "SELECT COUNT(*) FROM link_cliques WHERE slug = ?", (slug,)
            ).fetchone()[0]
            hora_row = con.execute(
                """SELECT strftime('%H', clicado_em) as hora, COUNT(*) as cnt
                   FROM link_cliques
                   WHERE slug = ? AND clicado_em > ?
                   GROUP BY hora ORDER BY cnt DESC LIMIT 1""",
                (slug, limite_24h),
            ).fetchone()
            hora_pico = f"{int(hora_row[0])}h-{int(hora_row[0])+1}h" if hora_row else None
            result.append({
                "slug": slug,
                "url_destino": url_destino,
                "produto": produto or "",
                "criado_em": criado_em,
                "total_cliques": total,
                "hora_pico": hora_pico,
            })
    return result
```

- [ ] **Step 3: Verify tables are created**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "from db import init_db; init_db(); import sqlite3, os; con = sqlite3.connect(os.getenv('DB_FILE','ofertas.db')); print(con.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())"
```

Expected output includes: `links` and `link_cliques` in the list.

- [ ] **Step 4: Commit**

```bash
git add db.py
git commit -m "feat: add link tracker tables and functions to db.py"
```

---

### Task 2: Add slug generator and wire into `bot.py`

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Add imports at top of `bot.py`**

After the existing `import os` line, add `re` and `unicodedata` to the imports (they are stdlib — no install needed):

```python
import re
import unicodedata
```

- [ ] **Step 2: Add `gerar_slug()` function after the `ler_categorias()` function (before `montar_mensagem`)**

```python
def gerar_slug(produto: str, loja: str) -> str:
    texto = f"{produto}-{loja}".lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:60]
```

- [ ] **Step 3: Add `BASE_URL` constant after the other config constants (near top, after `HORARIOS_EXECUCAO`)**

```python
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000").rstrip("/")
```

- [ ] **Step 4: Add new db imports to the existing import block in `bot.py`**

Find the line:
```python
from filtros import filtrar_melhores_ofertas, remover_repetidas, salvar_em_historico
```

Add after it:
```python
from db import criar_ou_buscar_link
```

- [ ] **Step 5: Modify `montar_mensagem()` to use tracked link**

Replace the existing `montar_mensagem` function body. The only change is replacing `oferta['link_afiliado']` with a tracked URL. Full replacement:

```python
def montar_mensagem(oferta: dict) -> str:
    preco_atual = oferta["preco_atual"]
    preco_antigo = oferta.get("preco_antigo")
    desconto = oferta.get("desconto_percentual", 0)

    slug = gerar_slug(oferta["produto"], oferta.get("loja", ""))
    criar_ou_buscar_link(slug, oferta["link_afiliado"], oferta["produto"])
    link_rastreado = f"{BASE_URL}/r/{slug}"

    if preco_antigo:
        economia = preco_antigo - preco_atual
        headline = f"🔥 BAIXOU R$ {economia:.2f} (-{desconto:.0f}%)"
    else:
        headline = f"🔥 OFERTA -{desconto:.0f}%"

    linhas = [headline, "", f"🛍️ {oferta['produto']}"]

    rating = oferta.get("rating")
    num_reviews = oferta.get("num_reviews")
    if rating and num_reviews:
        if num_reviews >= 1000:
            reviews_fmt = f"{num_reviews/1000:.1f}k"
        else:
            reviews_fmt = str(num_reviews)
        linhas.append(f"⭐ {rating:.1f} ({reviews_fmt} avaliações)")

    linhas.append("")
    if preco_antigo:
        linhas.append(f"❌ De: R$ {preco_antigo:.2f}")
    linhas.append(f"✅ Por: R$ {preco_atual:.2f}")
    if preco_antigo:
        linhas.append(f"💸 Você economiza R$ {preco_antigo - preco_atual:.2f}")

    linhas.extend([
        "",
        f"👉 {link_rastreado}",
        "",
        "⏰ Estoque limitado — preço pode mudar.",
    ])

    return "\n".join(linhas)
```

- [ ] **Step 6: Verify slug generation works**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "
import sys; sys.path.insert(0, '.')
from bot import gerar_slug
print(gerar_slug('iPhone 15 Pro 256GB', 'amazon'))
print(gerar_slug('Tênis Nike Air Max Feminino', 'kabum'))
"
```

Expected output:
```
iphone-15-pro-256gb-amazon
tenis-nike-air-max-feminino-kabum
```

- [ ] **Step 7: Commit**

```bash
git add bot.py
git commit -m "feat: add gerar_slug and wire tracked links into montar_mensagem"
```

---

### Task 3: Add Flask routes

**Files:**
- Modify: `painel/app.py`

- [ ] **Step 1: Update db import line in `painel/app.py`**

Find:
```python
from db import init_db, listar_ofertas
```

Replace with:
```python
from db import init_db, listar_ofertas, buscar_url_destino, registrar_clique, listar_links_com_stats
```

- [ ] **Step 2: Add the two new routes at the end of `painel/app.py`, before `if __name__ == "__main__":`**

```python
@app.route("/r/<slug>")
def redirect_link(slug):
    url = buscar_url_destino(slug)
    if not url:
        return "Link não encontrado", 404
    registrar_clique(slug)
    return redirect(url, code=302)


@app.route("/api/links")
@login_required
def api_links():
    return jsonify(listar_links_com_stats())
```

- [ ] **Step 3: Verify routes load without error**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "from painel.app import app; print([r.rule for r in app.url_map.iter_rules() if 'link' in r.rule or '/r/' in r.rule])"
```

Expected output includes `/r/<slug>` and `/api/links`.

- [ ] **Step 4: Commit**

```bash
git add painel/app.py
git commit -m "feat: add /r/<slug> redirect and /api/links routes"
```

---

### Task 4: Add Links card to dashboard

**Files:**
- Modify: `painel/templates/index.html`

- [ ] **Step 1: Add Links card HTML**

After the closing `</div>` of the "Últimas ofertas enviadas" card (line 73, `</div>`), add a new full-width card:

```html
    <!-- Links rastreados -->
    <div class="card" style="grid-column: 1 / -1;">
      <h3>🔗 Links Rastreados</h3>
      <table>
        <thead><tr><th>Produto</th><th>Slug</th><th>Cliques</th><th>Pico (24h)</th><th>Criado em</th></tr></thead>
        <tbody id="tabela-links"></tbody>
      </table>
    </div>
```

- [ ] **Step 2: Add JS function `carregarLinks()` and polling**

Inside the `<script>` block, after the `carregarOfertas()` function definition, add:

```javascript
    async function carregarLinks() {
      const links = await get('/api/links');
      const tbody = document.getElementById('tabela-links');
      if (!links.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="color:#999">Nenhum link registrado ainda.</td></tr>';
        return;
      }
      tbody.innerHTML = links.map(l => `
        <tr>
          <td>${(l.produto || '').substring(0, 45)}</td>
          <td><code>${l.slug}</code></td>
          <td>${l.total_cliques}</td>
          <td>${l.hora_pico || '—'}</td>
          <td>${new Date(l.criado_em).toLocaleString('pt-BR')}</td>
        </tr>`).join('');
    }
```

- [ ] **Step 3: Wire `carregarLinks()` into startup and polling**

Find the line:
```javascript
    carregarStatus(); carregarConfig(); carregarCategorias(); carregarOfertas();
    setInterval(carregarStatus, 15000);
```

Replace with:
```javascript
    carregarStatus(); carregarConfig(); carregarCategorias(); carregarOfertas(); carregarLinks();
    setInterval(carregarStatus, 15000);
    setInterval(carregarLinks, 30000);
```

- [ ] **Step 4: Commit**

```bash
git add painel/templates/index.html
git commit -m "feat: add Links Rastreados card to dashboard"
```

---

### Task 5: Update config.env.example

**Files:**
- Modify: `config.env.example`

- [ ] **Step 1: Add `BASE_URL` to config.env.example**

Add at the end of `config.env.example`:

```
# URL pública do serviço (Railway URL sem trailing slash)
BASE_URL=http://localhost:5000
```

- [ ] **Step 2: Commit**

```bash
git add config.env.example
git commit -m "docs: add BASE_URL to config.env.example"
```

---

### Task 6: End-to-end smoke test

- [ ] **Step 1: Run a dry-run to generate a tracked link**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "
import os; os.environ['DRY_RUN'] = 'true'; os.environ['DB_FILE'] = '/tmp/test_tracker.db'
from db import init_db; init_db()
from bot import gerar_slug, montar_mensagem, BASE_URL
oferta = {
    'produto': 'Teste Produto XYZ',
    'loja': 'amazon',
    'preco_atual': 99.90,
    'preco_antigo': 149.90,
    'desconto_percentual': 33,
    'link_afiliado': 'https://amzn.to/test123',
}
msg = montar_mensagem(oferta)
print(msg)
"
```

Expected: message contains `http://localhost:5000/r/teste-produto-xyz-amazon`

- [ ] **Step 2: Verify link saved in DB**

```bash
python3 -c "
import os; os.environ['DB_FILE'] = '/tmp/test_tracker.db'
from db import listar_links_com_stats
print(listar_links_com_stats())
"
```

Expected: list with one entry, slug `teste-produto-xyz-amazon`, `total_cliques: 0`.

- [ ] **Step 3: Simulate a click**

```bash
python3 -c "
import os; os.environ['DB_FILE'] = '/tmp/test_tracker.db'
from db import registrar_clique, buscar_url_destino
registrar_clique('teste-produto-xyz-amazon')
print(buscar_url_destino('teste-produto-xyz-amazon'))
"
```

Expected: `https://amzn.to/test123`

- [ ] **Step 4: Clean up test DB**

```bash
rm /tmp/test_tracker.db
```

- [ ] **Step 5: Add `BASE_URL` to Railway env vars**

In the Railway dashboard, add environment variable:
```
BASE_URL=https://<seu-servico>.up.railway.app
```

(Replace `<seu-servico>` with the actual Railway service URL.)

- [ ] **Step 6: Final commit**

```bash
git add -A
git status  # verify nothing unexpected staged
git commit -m "chore: link tracker complete"
```
