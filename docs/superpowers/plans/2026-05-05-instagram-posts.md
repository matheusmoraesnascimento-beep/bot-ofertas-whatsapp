# Instagram Posts Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar 3 posts Instagram (imagem 1080x1080 + caption) por dia com top descontos do DB, salvar em `posts/YYYY-MM-DD/` e exibir no painel Flask.

**Architecture:** Script isolado `instagram_posts.py` com função `gerar_posts_instagram()`. Bot.py chama a função uma vez por dia às 08h via flag de data. Flask expõe rota `/instagram-posts` com template listando posts do dia.

**Tech Stack:** Python, Pillow 9, curl_cffi, Flask, SQLite (db.py)

---

### Task 1: Função DB — top 3 ofertas últimas 24h

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Adicionar função `top_ofertas_para_post`**

```python
def top_ofertas_para_post(n: int = 3) -> list[dict]:
    limite = (datetime.now() - timedelta(hours=24)).isoformat()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT produto, loja, preco, link, desconto, imagem, data_envio
            FROM ofertas_enviadas
            WHERE data_envio > ?
            GROUP BY produto
            ORDER BY desconto DESC
            LIMIT ?
            """,
            (limite, n),
        ).fetchall()
    cols = ["produto", "loja", "preco", "link", "desconto", "imagem", "data_envio"]
    return [dict(zip(cols, r)) for r in rows]
```

Adicionar ao final de `db.py`, antes do último bloco.

- [ ] **Step 2: Testar no terminal**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "
from db import top_ofertas_para_post
r = top_ofertas_para_post()
print(f'ofertas: {len(r)}')
for o in r: print(o['produto'][:50], o['desconto'])
"
```

Esperado: 0-3 dicts (depende do DB atual). Sem erro.

- [ ] **Step 3: Commit**

```bash
git add db.py
git commit -m "feat: top_ofertas_para_post query para gerador Instagram"
```

---

### Task 2: Script `instagram_posts.py` — geração imagem + caption

**Files:**
- Create: `instagram_posts.py`

- [ ] **Step 1: Criar arquivo**

```python
import os
import io
import logging
import textwrap
from datetime import datetime
from pathlib import Path

from curl_cffi import requests as cffi_requests
from PIL import Image, ImageDraw, ImageFont

from db import top_ofertas_para_post

logger = logging.getLogger(__name__)

POSTS_DIR = Path("posts")
IMG_SIZE = 1080

# Cores
COR_FUNDO = (255, 255, 255)
COR_BADGE = (220, 38, 38)       # vermelho
COR_PRECO_ATUAL = (220, 38, 38)
COR_PRECO_ANTIGO = (150, 150, 150)
COR_RODAPE_BG = (245, 245, 245)
COR_TEXTO = (30, 30, 30)
COR_LOJA = (80, 80, 80)


def _baixar_imagem(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        r = cffi_requests.get(url, timeout=10, impersonate="chrome124")
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"Falha download imagem: {e}")
        return None


def _fonte(tamanho: int, negrito: bool = False):
    """Tenta carregar fonte do sistema; fallback ImageFont default."""
    candidatos_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidatos_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidatos = candidatos_bold if negrito else candidatos_regular
    for path in candidatos:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, tamanho)
            except Exception:
                continue
    return ImageFont.load_default()


def _gerar_imagem(oferta: dict, indice: int) -> Image.Image:
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), COR_FUNDO)
    draw = ImageDraw.Draw(img)

    # --- Foto do produto (área: y=80 até y=680) ---
    foto = _baixar_imagem(oferta.get("imagem"))
    if foto:
        foto_rgb = foto.convert("RGB")
        foto_rgb.thumbnail((900, 600), Image.LANCZOS)
        fx = (IMG_SIZE - foto_rgb.width) // 2
        fy = 80 + (600 - foto_rgb.height) // 2
        img.paste(foto_rgb, (fx, fy))
    else:
        # Fallback: fundo colorido com nome
        cores_fallback = [(255, 237, 213), (219, 234, 254), (220, 252, 231)]
        cor = cores_fallback[indice % len(cores_fallback)]
        draw.rectangle([0, 0, IMG_SIZE, 700], fill=cor)
        fonte_fb = _fonte(48, negrito=True)
        nome_curto = oferta["produto"][:60]
        draw.text((540, 380), nome_curto, fill=COR_TEXTO, font=fonte_fb, anchor="mm")

    # --- Badge desconto (canto superior direito) ---
    desconto = int(oferta.get("desconto", 0))
    if desconto > 0:
        badge_txt = f"-{desconto}%"
        fonte_badge = _fonte(52, negrito=True)
        bw, bh = 180, 80
        bx, by = IMG_SIZE - bw - 20, 20
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, fill=COR_BADGE)
        draw.text((bx + bw // 2, by + bh // 2), badge_txt, fill="white",
                  font=fonte_badge, anchor="mm")

    # --- Rodapé (y=700 até y=1080) ---
    draw.rectangle([0, 700, IMG_SIZE, IMG_SIZE], fill=COR_RODAPE_BG)

    # Nome produto (quebra linha se necessário)
    nome_curto = textwrap.shorten(oferta["produto"], width=55, placeholder="...")
    fonte_nome = _fonte(38, negrito=True)
    draw.text((54, 720), nome_curto, fill=COR_TEXTO, font=fonte_nome)

    # Preços
    preco_atual = oferta.get("preco", 0) or 0
    fonte_preco_atual = _fonte(64, negrito=True)
    fonte_preco_antigo = _fonte(36)

    # Calcula preco_antigo a partir do desconto
    preco_antigo = None
    if desconto and desconto < 100 and preco_atual:
        preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

    y_preco = 800
    if preco_antigo:
        txt_antigo = f"R$ {preco_antigo:.2f}"
        draw.text((54, y_preco), txt_antigo, fill=COR_PRECO_ANTIGO, font=fonte_preco_antigo)
        # Risca o preço antigo
        bbox = draw.textbbox((54, y_preco), txt_antigo, font=fonte_preco_antigo)
        mid_y = (bbox[1] + bbox[3]) // 2
        draw.line([(bbox[0], mid_y), (bbox[2], mid_y)], fill=COR_PRECO_ANTIGO, width=2)
        y_preco += 46

    draw.text((54, y_preco), f"R$ {preco_atual:.2f}", fill=COR_PRECO_ATUAL,
              font=fonte_preco_atual)

    # Loja + CTA
    fonte_loja = _fonte(32)
    loja = oferta.get("loja", "")
    draw.text((54, 960), f"📍 {loja}", fill=COR_LOJA, font=fonte_loja)
    fonte_cta = _fonte(30, negrito=True)
    draw.text((54, 1010), "Comenta QUERO que mando o link 🔥", fill=COR_TEXTO,
              font=fonte_cta)

    return img


def _gerar_caption(oferta: dict) -> str:
    nome_curto = textwrap.shorten(oferta["produto"], width=60, placeholder="...")
    preco_atual = oferta.get("preco", 0) or 0
    desconto = int(oferta.get("desconto", 0))
    loja = oferta.get("loja", "")

    preco_antigo = None
    if desconto and desconto < 100 and preco_atual:
        preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

    linhas = [f"{nome_curto} 🔥", ""]
    if preco_antigo:
        linhas.append(f"De R${preco_antigo:.2f} por R${preco_atual:.2f} (-{desconto}%)")
    else:
        linhas.append(f"R${preco_atual:.2f} (-{desconto}%)")

    loja_tag = loja.lower().replace(" ", "").replace("ç", "c").replace("á", "a")
    linhas.extend([
        f"📍 {loja}",
        "",
        "Comenta QUERO que mando o link no direct 👇",
        "",
        f"#oferta #promocao #{loja_tag} #ofertas #desconto #economize",
    ])
    return "\n".join(linhas)


def gerar_posts_instagram(n: int = 3) -> list[Path]:
    ofertas = top_ofertas_para_post(n)
    if not ofertas:
        logger.warning("Instagram posts: sem ofertas nas últimas 24h")
        return []

    hoje = datetime.now().strftime("%Y-%m-%d")
    pasta = POSTS_DIR / hoje
    pasta.mkdir(parents=True, exist_ok=True)

    gerados = []
    for i, oferta in enumerate(ofertas, start=1):
        try:
            img = _gerar_imagem(oferta, i - 1)
            img_path = pasta / f"post_{i}.jpg"
            img.save(img_path, "JPEG", quality=92)

            caption = _gerar_caption(oferta)
            txt_path = pasta / f"post_{i}.txt"
            txt_path.write_text(caption, encoding="utf-8")

            gerados.append(img_path)
            logger.info(f"Instagram post {i} gerado: {oferta['produto'][:50]}")
        except Exception as e:
            logger.error(f"Erro gerando post {i}: {e}")

    return gerados


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    paths = gerar_posts_instagram()
    print(f"Gerados: {len(paths)}")
    for p in paths:
        print(" ", p)
```

- [ ] **Step 2: Testar geração**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 instagram_posts.py
```

Esperado:
```
INFO - Instagram posts: sem ofertas nas últimas 24h
Gerados: 0
```
(ou posts gerados se DB tiver dados recentes). Sem traceback.

- [ ] **Step 3: Forçar teste com oferta fake**

```bash
python3 -c "
from instagram_posts import _gerar_imagem, _gerar_caption
from pathlib import Path

oferta = {
    'produto': 'Fone Bluetooth JBL Tune 520BT Preto Sem Fio On Ear',
    'loja': 'Amazon',
    'preco': 189.0,
    'desconto': 37,
    'imagem': 'https://m.media-amazon.com/images/I/51olNZRjn+L._AC_UL320_.jpg',
    'link': 'https://amzn.to/test',
}
img = _gerar_imagem(oferta, 0)
img.save('/tmp/test_post.jpg', 'JPEG', quality=92)
print('Imagem salva em /tmp/test_post.jpg')
print(_gerar_caption(oferta))
"
```

Esperado: arquivo `/tmp/test_post.jpg` criado, caption impresso no terminal.

- [ ] **Step 4: Commit**

```bash
git add instagram_posts.py
git commit -m "feat: instagram_posts.py — gerador imagem+caption via Pillow"
```

---

### Task 3: Integrar ao bot.py — roda uma vez por dia às 08h

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Adicionar import e lógica de geração diária**

No topo de `bot.py`, após os imports existentes, adicionar:

```python
from instagram_posts import gerar_posts_instagram as _gerar_posts_ig
```

Adicionar função após `executar_rodada()`:

```python
def _posts_instagram_se_necessario():
    hoje = datetime.now().strftime("%Y-%m-%d")
    flag = f"posts/{hoje}/.gerado"
    if os.path.exists(flag):
        return
    hora = datetime.now().hour
    if hora < 8:
        return
    try:
        paths = _gerar_posts_ig(3)
        if paths:
            os.makedirs(f"posts/{hoje}", exist_ok=True)
            open(flag, "w").close()
            logger.info(f"Posts Instagram gerados: {len(paths)}")
    except Exception as e:
        logger.error(f"Erro gerando posts Instagram: {e}")
```

No loop `while True:` em `main()`, antes de `_aguardar_ate_proximo(HORARIOS_EXECUCAO)`, adicionar:

```python
        _posts_instagram_se_necessario()
```

- [ ] **Step 2: Verificar sintaxe**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "import bot; print('OK')"
```

Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "feat: gera posts Instagram uma vez por dia após 08h no loop do bot"
```

---

### Task 4: Rota Flask + template

**Files:**
- Modify: `painel/app.py`
- Create: `painel/templates/instagram_posts.html`

- [ ] **Step 1: Adicionar rotas no `painel/app.py`**

Antes do bloco `if __name__ == "__main__":`, adicionar:

```python
@app.route("/instagram-posts")
@login_required
def instagram_posts():
    from pathlib import Path
    hoje = datetime.now().strftime("%Y-%m-%d")
    pasta = Path("posts") / hoje
    posts = []
    if pasta.exists():
        for i in range(1, 4):
            img_path = pasta / f"post_{i}.jpg"
            txt_path = pasta / f"post_{i}.txt"
            if img_path.exists():
                caption = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
                posts.append({"indice": i, "caption": caption, "data": hoje})
    return render_template("instagram_posts.html", posts=posts, hoje=hoje)


@app.route("/api/instagram-posts/imagem/<data>/<filename>")
@login_required
def instagram_post_imagem(data, filename):
    from flask import send_from_directory
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        return "invalid", 400
    if not re.match(r"^post_[123]\.jpg$", filename):
        return "invalid", 400
    pasta = os.path.join("posts", data)
    return send_from_directory(pasta, filename)
```

Adicionar import `datetime` se não existir (já existe via `from datetime import datetime` — checar).

- [ ] **Step 2: Criar template `painel/templates/instagram_posts.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Posts Instagram</title>
  <style>
    body { font-family: sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
    h1 { color: #333; margin-bottom: 24px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
    .card { background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.1); overflow: hidden; }
    .card img { width: 100%; display: block; }
    .card-body { padding: 16px; }
    textarea { width: 100%; height: 140px; border: 1px solid #ddd; border-radius: 8px; padding: 8px;
               font-size: 13px; resize: vertical; box-sizing: border-box; }
    .actions { display: flex; gap: 8px; margin-top: 12px; }
    .btn { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
    .btn-copy { background: #3483fa; color: white; }
    .btn-dl { background: #00a650; color: white; text-decoration: none; display: inline-block; }
    .empty { text-align: center; color: #888; margin-top: 60px; font-size: 18px; }
    .back { display: inline-block; margin-bottom: 20px; color: #3483fa; text-decoration: none; }
  </style>
</head>
<body>
  <a class="back" href="/">← Voltar ao painel</a>
  <h1>Posts Instagram — {{ hoje }}</h1>

  {% if posts %}
  <div class="grid">
    {% for post in posts %}
    <div class="card">
      <img src="/api/instagram-posts/imagem/{{ post.data }}/post_{{ post.indice }}.jpg"
           alt="Post {{ post.indice }}">
      <div class="card-body">
        <textarea id="caption-{{ post.indice }}">{{ post.caption }}</textarea>
        <div class="actions">
          <button class="btn btn-copy" onclick="copiar({{ post.indice }})">Copiar caption</button>
          <a class="btn btn-dl"
             href="/api/instagram-posts/imagem/{{ post.data }}/post_{{ post.indice }}.jpg"
             download="post_{{ post.indice }}.jpg">Baixar imagem</a>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <p class="empty">Nenhum post gerado hoje ainda.<br>
    Posts são gerados automaticamente após as 08h quando há ofertas nas últimas 24h.</p>
  {% endif %}

  <script>
    function copiar(i) {
      const ta = document.getElementById('caption-' + i);
      ta.select();
      navigator.clipboard.writeText(ta.value).then(() => alert('Caption copiado!'));
    }
  </script>
</body>
</html>
```

- [ ] **Step 3: Adicionar link na navbar do `index.html`**

Localiza no `painel/templates/index.html` um link de navegação existente e adiciona após:

```html
<a href="/instagram-posts">Posts Instagram</a>
```

(Adapta ao padrão visual do template existente.)

- [ ] **Step 4: Testar rota**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -m flask --app painel/app.py run --port 5001 &
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/instagram-posts
```

Esperado: `302` (redirect para login — rota existe).

```bash
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add painel/app.py painel/templates/instagram_posts.html painel/templates/index.html
git commit -m "feat: aba Posts Instagram no painel — preview, copiar caption, download"
```

---

### Task 5: Adicionar Pillow ao requirements.txt e push

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Verificar e atualizar requirements.txt**

Conteúdo atual de `requirements.txt`:
```
playwright
requests
beautifulsoup4
python-dotenv
flask
curl_cffi
```

Adicionar `Pillow` se não estiver:

```
playwright
requests
beautifulsoup4
python-dotenv
flask
curl_cffi
Pillow
```

- [ ] **Step 2: Commit e push**

```bash
git add requirements.txt
git commit -m "chore: add Pillow to requirements"
git push
```
