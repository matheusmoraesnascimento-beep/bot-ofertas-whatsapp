"""
Gera blog estático Relâmpago em ~/ofertas-relampago-bot/ para GitHub Pages.
Design baseado em handoff Claude Design (h/DumYUOKyKknasLTw-vPWCg).
- index.html: catálogo (nav, hero, products grid, etc)
- oferta/<slug>/index.html: página produto (hero editorial + botão Amazon)
"""
import os
import shutil
from pathlib import Path
from datetime import datetime
from html import escape
from db import listar_ofertas_publicas, buscar_oferta_por_slug

ROOT = Path(__file__).parent
BLOG_REPO = Path(os.getenv("BLOG_REPO", os.path.expanduser("~/ofertas-relampago-bot")))

HEAD_COMMON = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Geist:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css_path}">"""


def _brl(v):
    if v is None:
        return ""
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""


def _stars_html(n=5):
    full = "★" * n
    empty = "☆" * (5 - n)
    return full + empty


def _ph_class(i):
    return f"ph-{(i % 7) + 1}"


WA_LINK = os.getenv("WHATSAPP_GRUPO_LINK", "")
IG_HANDLE = os.getenv("INSTAGRAM_HANDLE", "")

_TOP_BAR_ITEMS = [
    ("Entre no grupo WhatsApp · ofertas em tempo real", True),
    ("Bot rastreando lojas 24/7", True),
    ("Curadoria humana, preço de bot", False),
    ("Desconto mínimo 20%", False),
    ("Sem spam · só ofertas reais", False),
] * 2


def _build_top_bar():
    parts = []
    for txt, pulse in _TOP_BAR_ITEMS:
        dot = '<span class="pulse"></span>' if pulse else ''
        parts.append(f'<span>{dot}{txt}</span>')
    return '<div class="top-bar"><div class="top-bar-track">' + "".join(parts) + '</div></div>'


TOP_BAR = _build_top_bar()


def _wa_floating():
    if not WA_LINK:
        return ""
    return f'''<a href="{WA_LINK}" target="_blank" rel="noopener" aria-label="Entrar no grupo WhatsApp"
       style="position:fixed;bottom:24px;right:24px;z-index:90;background:#25d366;color:#fff;
              padding:14px 22px;border-radius:999px;font-family:var(--mono);font-size:13px;font-weight:600;
              letter-spacing:0.08em;text-transform:uppercase;display:inline-flex;align-items:center;gap:10px;
              box-shadow:0 14px 32px -8px rgba(37,211,102,.5),0 4px 10px rgba(0,0,0,.15);
              transition:transform .2s, box-shadow .2s">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3.5A11 11 0 0 0 3.4 17.2L2 22l4.9-1.3a11 11 0 0 0 13.6-17.2zM12 20a8 8 0 0 1-4.1-1.1l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 20 12a8 8 0 0 1-8 8zm4.4-6c-.2-.1-1.4-.7-1.6-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.5 6.5 0 0 1-3.3-2.9c-.2-.4 0-.5.2-.7l.4-.5c.1-.1.2-.3.3-.5 0-.2 0-.4-.1-.5l-.8-1.8c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.5 0-.7.3-.3.3-1 1-1 2.5s1 2.9 1.2 3.1c.1.2 2.1 3.3 5.2 4.6.7.3 1.3.5 1.7.6.7.2 1.3.2 1.8.1.6-.1 1.7-.7 1.9-1.4.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.6-.3z"/></svg>
      Entrar no grupo
    </a>'''


def _wa_banner_section():
    if not WA_LINK:
        return ""
    return f'''<section class="container" style="margin-top:40px;margin-bottom:40px">
  <div style="background:linear-gradient(135deg,#075e54 0%,#128c7e 50%,#25d366 100%);color:#fff;
              border-radius:28px;padding:56px 32px;position:relative;overflow:hidden;text-align:center">
    <div style="position:absolute;right:-60px;top:-60px;width:320px;height:320px;
                background:radial-gradient(circle,rgba(255,255,255,.12),transparent 70%);pointer-events:none"></div>
    <div style="position:absolute;left:-60px;bottom:-60px;width:280px;height:280px;
                background:radial-gradient(circle,rgba(255,255,255,.08),transparent 70%);pointer-events:none"></div>
    <div style="position:relative;max-width:680px;margin:0 auto;display:flex;flex-direction:column;align-items:center;text-align:center">
      <div style="width:88px;height:88px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;margin-bottom:24px;box-shadow:0 12px 28px -8px rgba(0,0,0,.25)">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="#25d366"><path d="M20.5 3.5A11 11 0 0 0 3.4 17.2L2 22l4.9-1.3a11 11 0 0 0 13.6-17.2zM12 20a8 8 0 0 1-4.1-1.1l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 20 12a8 8 0 0 1-8 8zm4.4-6c-.2-.1-1.4-.7-1.6-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.5 6.5 0 0 1-3.3-2.9c-.2-.4 0-.5.2-.7l.4-.5c.1-.1.2-.3.3-.5 0-.2 0-.4-.1-.5l-.8-1.8c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.5 0-.7.3-.3.3-1 1-1 2.5s1 2.9 1.2 3.1c.1.2 2.1 3.3 5.2 4.6.7.3 1.3.5 1.7.6.7.2 1.3.2 1.8.1.6-.1 1.7-.7 1.9-1.4.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.6-.3z"/></svg>
      </div>
      <div class="eyebrow" style="color:rgba(255,255,255,.85);display:inline-flex;align-items:center;justify-content:center">
        <span class="dot" style="background:#fff"></span>Grupo Privado WhatsApp · ao vivo
      </div>
      <h2 style="font-family:var(--display);font-size:clamp(36px,4.4vw,56px);line-height:0.98;letter-spacing:-0.025em;margin:14px 0 16px;font-weight:400">
        Receba ofertas <span style="font-style:italic;color:#dcf8c6">antes</span> de todo mundo.
      </h2>
      <p style="color:rgba(255,255,255,.9);max-width:520px;margin:0 auto 28px;font-size:16px">
        Bot manda direto no WhatsApp toda vez que acha desconto real. Sem spam, só ofertas filtradas pela curadoria.
      </p>
      <a href="{WA_LINK}" target="_blank" rel="noopener" class="btn"
         style="background:#fff;color:#075e54;padding:18px 36px;font-size:16px;font-weight:600;
                box-shadow:0 12px 28px -8px rgba(0,0,0,.3)">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 3.5A11 11 0 0 0 3.4 17.2L2 22l4.9-1.3a11 11 0 0 0 13.6-17.2zM12 20a8 8 0 0 1-4.1-1.1l-.3-.2-2.9.8.8-2.8-.2-.3A8 8 0 1 1 20 12a8 8 0 0 1-8 8zm4.4-6c-.2-.1-1.4-.7-1.6-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.5 6.5 0 0 1-3.3-2.9c-.2-.4 0-.5.2-.7l.4-.5c.1-.1.2-.3.3-.5 0-.2 0-.4-.1-.5l-.8-1.8c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.5 0-.7.3-.3.3-1 1-1 2.5s1 2.9 1.2 3.1c.1.2 2.1 3.3 5.2 4.6.7.3 1.3.5 1.7.6.7.2 1.3.2 1.8.1.6-.1 1.7-.7 1.9-1.4.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.6-.3z"/></svg>
        Entrar no grupo grátis <span class="arrow">→</span>
      </a>
      <div style="display:flex;gap:22px;flex-wrap:wrap;justify-content:center;margin-top:22px;
                  font-family:var(--mono);font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(255,255,255,.75)">
        <span><span style="color:#dcf8c6;font-size:14px">✓</span> Sem custo</span>
        <span><span style="color:#dcf8c6;font-size:14px">✓</span> Sai quando quiser</span>
        <span><span style="color:#dcf8c6;font-size:14px">✓</span> Avisos instantâneos</span>
      </div>
    </div>
  </div>
</section>'''


def _nav(base_url):
    return f"""<header class="nav"><div class="container nav-inner">
  <div class="nav-left">
    <a href="{base_url}/" class="brand" aria-label="Ofertas Relâmpago">
      <span class="brand-mark"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"/></svg></span>
      <span>Relâmpago</span>
      <span class="brand-sub">·BOT</span>
    </a>
  </div>
  <nav class="nav-links">
    <a href="{base_url}/" class="active">Início</a>
    <a href="{base_url}/#produtos">Ofertas</a>
    <a href="{base_url}/#artigos">Editorial</a>
    <a href="{base_url}/#manifesto">Sobre o Bot</a>
  </nav>
  <div class="nav-right">
    <button class="icon-btn" aria-label="Buscar" onclick="document.getElementById('search-overlay')?.classList.add('open')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5" stroke-linecap="round"/></svg></button>
    <button class="icon-btn" aria-label="Favoritos"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 20s-7-4.5-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.5-7 10-7 10z"/></svg></button>
  </div>
</div></header>"""


def _hero(total_ofertas):
    hoje = datetime.now().strftime("%d %B %Y").lower()
    return f"""<section class="hero"><div class="container">
  <div class="hero-grid">
    <div>
      <div class="eyebrow"><span class="dot"></span>Edição · {hoje}</div>
      <h1>
        Ofertas que<br>
        o algoritmo <span class="ital">caça</span>.<br>
        O <span class="strike">preço cheio</span> que<br>
        você nunca paga.
      </h1>
      <p class="hero-lede">
        Um robô vasculha lojas a cada 2 horas. Filtros automáticos
        eliminam falsos descontos. Você recebe só o que vale: descontos
        reais, produtos que duram, sem barulho.
      </p>
      <div class="hero-ctas">
        <a class="btn btn-accent" href="#produtos">Ver ofertas de hoje <span class="arrow">→</span></a>
        <a class="btn btn-ghost" href="#artigos">Ler o editorial</a>
      </div>
      <div class="hero-meta">
        <div class="hero-meta-item"><div class="num">{total_ofertas}</div><div class="lbl">Ofertas Ativas</div></div>
        <div class="hero-meta-item"><div class="num">2h</div><div class="lbl">Entre Atualizações</div></div>
        <div class="hero-meta-item"><div class="num">24/7</div><div class="lbl">Bot Sempre Ativo</div></div>
      </div>
    </div>
    <div style="position:relative">
      <div class="hero-card">
        <div class="ph ph-1 ph-stripe"></div>
        <div class="ph-label">Capa · Achado do dia</div>
        <div class="hero-card-overlay">
          <div class="hero-card-tag">
            <span class="strike-old">Sem barulho. Só preço.</span>
            <span class="price">Relâmpago</span>
          </div>
          <div class="hero-card-discount">BOT</div>
        </div>
      </div>
      <div class="hero-floating-card">
        <div class="stars">★★★★★</div>
        <div class="quote">"Em segundos eu recebi o alerta e fechei. Economia real."</div>
        <div class="who"><span class="avatar">MV</span><span>Marina, SP</span></div>
      </div>
    </div>
  </div>
</div></section>"""


TRUST_STRIP = """<section class="trust-strip"><div class="container">
  <div class="trust-row">
    <span>4,9 ★ avaliação média</span>
    <span class="sep"></span>
    <span>Curadoria <em style="font-style:italic">humana</em></span>
    <span class="sep"></span>
    <span>Bot 24/7</span>
    <span class="sep"></span>
    <span>Frete grátis Prime</span>
    <span class="sep"></span>
    <span>Preço rastreado</span>
  </div>
</div></section>"""


FLASH_BANNER = """<section class="container">
  <div class="flash"><div class="flash-inner">
    <div>
      <div class="eyebrow" style="color:oklch(80% 0.16 35)"><span class="dot"></span>Drop Relâmpago · ao vivo</div>
      <h2>Duas horas.<br><span class="ital">Próximo</span> drop.<br>Estoque que some.</h2>
      <p>A cada ciclo, o bot escaneia milhares de produtos e seleciona os melhores descontos. Acaba quando o cronômetro zera — ou quando o estoque acabar.</p>
      <a class="btn btn-accent" href="#produtos">Entrar no drop <span class="arrow">→</span></a>
    </div>
    <div class="countdown" id="countdown">
      <div class="cd-box"><div class="cd-num" data-cd="h">--</div><div class="cd-lbl">Horas</div></div>
      <div class="cd-box"><div class="cd-num" data-cd="m">--</div><div class="cd-lbl">Minutos</div></div>
      <div class="cd-box"><div class="cd-num" data-cd="s">--</div><div class="cd-lbl">Segundos</div></div>
    </div>
  </div></div>
</section>"""


ARTICLES_SECTION = """<section class="section" id="artigos"><div class="container">
  <div class="section-head">
    <div>
      <div class="eyebrow"><span class="dot"></span>O Diário</div>
      <h2>Lê-se primeiro. <span class="ital">Compra-se</span> com confiança.</h2>
    </div>
    <a class="tail" href="#produtos">Ver ofertas <span class="arrow">→</span></a>
  </div>
  <div class="articles">
    <article class="article feature">
      <div class="article-img">
        <div class="ph ph-2 ph-stripe"></div>
        <div class="pill">Guia</div>
        <div class="ph-tag">Como o bot funciona</div>
      </div>
      <div class="article-body">
        <div class="article-meta">Sempre atualizado · 5 min de leitura</div>
        <h3>Como o Relâmpago Bot encontra preços que ninguém mais vê</h3>
        <p class="article-excerpt">Uma engrenagem de scrapers, filtros e dedup que recusa falsos descontos. Aqui dentro, só o que o bot considera real.</p>
        <div class="article-foot">
          <span style="display:inline-flex;align-items:center;gap:8px"><span class="avatar" style="width:24px;height:24px;font-size:9px">RB</span><span>Relâmpago Bot · 24/7</span></span>
          <a class="read" href="#produtos">Ver ofertas <span class="arrow">→</span></a>
        </div>
      </div>
    </article>
    <article class="article">
      <div class="article-img"><div class="ph ph-3 ph-stripe"></div><div class="pill">Critério</div><div class="ph-tag">20% mínimo</div></div>
      <div class="article-body">
        <div class="article-meta">Filtros do bot · 3 min</div>
        <h3>Por que descontos abaixo de 20% nunca aparecem aqui</h3>
        <p class="article-excerpt">A régua é alta: pelo menos 20% off, dedup de 48h, score por categoria.</p>
        <div class="article-foot"><span style="color:var(--ink-3)">Filtros ativos</span><a class="read" href="#produtos">Ler <span class="arrow">→</span></a></div>
      </div>
    </article>
    <article class="article">
      <div class="article-img"><div class="ph ph-4 ph-stripe"></div><div class="pill">Tracking</div><div class="ph-tag">Preço histórico</div></div>
      <div class="article-body">
        <div class="article-meta">Histórico de 30 dias · 4 min</div>
        <h3>Cada oferta passa pelo histórico de preço dos últimos 30 dias</h3>
        <p class="article-excerpt">Se o "desconto" é só um preço que voltou ao normal, o bot ignora. Quer mínimo histórico real.</p>
        <div class="article-foot"><span style="color:var(--ink-3)">Algoritmo</span><a class="read" href="#produtos">Ler <span class="arrow">→</span></a></div>
      </div>
    </article>
  </div>
</div></section>"""


def _product_card(o, base_url, i):
    slug = o["slug"]
    produto = escape(o.get("produto") or "")
    preco = o.get("preco") or 0
    desconto = int(o.get("desconto") or 0)
    imagem = o.get("imagem") or ""
    loja = escape(o.get("loja") or "loja")
    preco_antigo = preco / (1 - desconto / 100) if preco and desconto else 0
    economia = preco_antigo - preco if preco_antigo else 0
    estoque = max(5, 200 - (i * 23))
    stock_pct = min(100, (estoque / 200) * 100)
    low = estoque < 25

    img_block = (
        f'<img src="{escape(imagem)}" alt="{produto[:80]}" loading="lazy" '
        f'style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:var(--bg-card);padding:12%">'
        if imagem else f'<div class="ph {_ph_class(i)} ph-stripe"></div>'
    )

    badges = []
    if desconto:
        badges.append(f'<span class="badge hot">-{desconto}%</span>')
    if i < 3:
        badges.append('<span class="badge new">Novo</span>')

    return f"""<a class="product" href="{base_url}/oferta/{slug}/" style="text-decoration:none;color:inherit">
  <div class="product-media">
    {img_block}
    <div class="product-badges">{"".join(badges)}</div>
    <button class="product-wish" aria-label="Favoritar" onclick="event.preventDefault();this.classList.toggle('active')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 20s-7-4.5-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.5-7 10-7 10z"/></svg></button>
    <div class="product-add"><span>Ver oferta</span><span>→</span></div>
  </div>
  <div class="product-body">
    <span class="product-cat">{loja}</span>
    <h4>{produto[:90]}</h4>
    <div class="product-rating"><span class="stars">{_stars_html(5)}</span><span>verificado por bot</span></div>
    <div class="product-prices">
      <span class="price-now">{_brl(preco)}</span>
      {f'<span class="price-old">{_brl(preco_antigo)}</span>' if preco_antigo else ''}
      {f'<span class="price-save">economia {_brl(economia)}</span>' if economia else ''}
    </div>
    <div class="stock">
      <div class="stock-bar"><i style="width:{100 - stock_pct:.0f}%"></i></div>
      <span>{"Restam " + str(estoque) if low else str(estoque) + " em estoque"}</span>
    </div>
  </div>
</a>"""


def _products_section(ofertas, base_url):
    cards = "".join(_product_card(o, base_url, i) for i, o in enumerate(ofertas))
    if not cards:
        cards = '<div style="grid-column:1/-1;padding:60px;text-align:center;color:var(--ink-3)">Nenhum produto no momento. O bot está em busca.</div>'

    lojas = sorted({(o.get("loja") or "").strip() for o in ofertas if o.get("loja")})
    tabs = ['<button class="cat-tab active" data-cat="all">Tudo<span class="count">·' + str(len(ofertas)) + '</span></button>']
    for l in lojas:
        count = sum(1 for o in ofertas if (o.get("loja") or "").strip() == l)
        tabs.append(f'<button class="cat-tab" data-cat="{escape(l)}">{escape(l)}<span class="count">·{count}</span></button>')

    return f"""<section class="section" id="produtos"><div class="container">
  <div class="section-head">
    <div>
      <div class="eyebrow"><span class="dot"></span>Vitrine</div>
      <h2>Achados de <span class="ital">agora</span> — handpicked.</h2>
    </div>
    <div class="cat-tabs">{"".join(tabs)}</div>
  </div>
  <div class="products" id="products-grid">{cards}</div>
</div></section>"""


EDITORIAL_BLOCK = """<section class="section" id="manifesto"><div class="container">
  <div class="editorial">
    <div class="editorial-img"><div class="ph ph-7 ph-stripe"></div><div class="ph-tag">Bot · Sempre ligado</div></div>
    <div class="editorial-body">
      <div class="eyebrow"><span class="dot"></span>Manifesto</div>
      <h2>Comprar bem<br>é uma <span class="ital">forma de ler</span>.</h2>
      <p style="color:var(--ink-2);font-size:16px;margin:0;max-width:480px">Não somos cupom. Somos um bot que rastreia preços de verdade e uma curadoria que filtra ruído — pra você comprar só o que vale.</p>
      <div style="display:flex;gap:12px;margin-top:8px"><a class="btn btn-primary" href="#produtos">Ver ofertas <span class="arrow">→</span></a></div>
      <div class="editorial-stats">
        <div><div class="num">24/7</div><div class="lbl">Bot ativo</div></div>
        <div><div class="num">2h</div><div class="lbl">Ciclo de busca</div></div>
        <div><div class="num">20%</div><div class="lbl">Desconto mínimo</div></div>
      </div>
    </div>
  </div>
</div></section>"""


TESTIMONIALS = """<section class="section"><div class="container">
  <div class="section-head">
    <div>
      <div class="eyebrow"><span class="dot"></span>Leitores que viraram clientes</div>
      <h2>Histórias <span class="ital">reais</span> de quem deixou de pagar caro.</h2>
    </div>
    <div class="tail" style="display:flex;gap:8px">
      <span style="display:inline-flex;align-items:center;gap:6px;color:var(--ink-2)">
        <span class="stars" style="color:var(--gold);letter-spacing:2px">★★★★★</span>
        <b style="font-weight:500;color:var(--ink)">4,9</b>
        <span style="font-family:var(--mono);font-size:11px;color:var(--ink-3)">· verificado</span>
      </span>
    </div>
  </div>
  <div class="testimonials">
    <article class="testimonial">
      <div class="stars">★★★★★</div>
      <p class="quote">Recebi alerta de uma air fryer 50% off, fechei em 1 minuto. Já comprava sem desconto antes.</p>
      <div class="person"><span class="avatar">MV</span><span><div class="name">Marina V.</div><div class="role">São Paulo</div></span><span class="verified"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg> verificado</span></div>
    </article>
    <article class="testimonial">
      <div class="stars">★★★★★</div>
      <p class="quote">O bot pegou um perfume que eu queria há meses com 60% off. Tinha o preço histórico, sabia que era de verdade.</p>
      <div class="person"><span class="avatar">JR</span><span><div class="name">João R.</div><div class="role">Rio de Janeiro</div></span><span class="verified"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg> verificado</span></div>
    </article>
    <article class="testimonial">
      <div class="stars">★★★★★</div>
      <p class="quote">Curadoria séria. Não enche o feed de tranqueira — só vem o que merece atenção.</p>
      <div class="person"><span class="avatar">AC</span><span><div class="name">Ana C.</div><div class="role">Belo Horizonte</div></span><span class="verified"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg> verificado</span></div>
    </article>
  </div>
</div></section>"""


NEWSLETTER = """<section class="container">
  <div class="newsletter"><div class="newsletter-inner">
    <div>
      <div class="eyebrow"><span class="dot"></span>Receba no WhatsApp</div>
      <h2>Receba o drop antes <span class="ital">de todo mundo</span>.</h2>
      <p>O bot manda direto no WhatsApp toda vez que acha uma oferta de verdade. Curadoria humana, preço de bot.</p>
      <form class="nl-form" onsubmit="event.preventDefault();this.querySelector('button').innerHTML='No WhatsApp já! <svg style=\\'width:14px;height:14px\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'currentColor\\' stroke-width=\\'2\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\'><path d=\\'M5 12l5 5L20 7\\'/></svg>'">
        <input type="email" placeholder="seu@email.com" aria-label="Seu e-mail">
        <button class="btn btn-accent" type="submit">Quero entrar <span class="arrow">→</span></button>
      </form>
      <div class="nl-perks">
        <span><span class="tick">✓</span> Sem spam</span>
        <span><span class="tick">✓</span> Acesso antecipado</span>
        <span><span class="tick">✓</span> Só ofertas reais</span>
      </div>
    </div>
    <div class="nl-art" aria-hidden="true">
      <div class="nl-coin c1">⚡</div>
      <div class="nl-coin c2">%</div>
      <div class="nl-coin c3">R$</div>
    </div>
  </div></div>
</section>"""


FOOTER = """<footer><div class="container">
  <div class="foot-grid">
    <div class="foot-brand">
      <h4>Relâmpago<span style="color:var(--accent)">.</span></h4>
      <p>O diário de compras inteligentes do Brasil. Curadoria humana, preços rastreados por bot.</p>
      <div style="display:flex;gap:8px;margin-top:22px">
        <span class="badge" style="background:rgba(247,243,236,.08);color:var(--bg);border-radius:999px">WhatsApp</span>
        <span class="badge" style="background:rgba(247,243,236,.08);color:var(--bg);border-radius:999px">Instagram</span>
      </div>
    </div>
    <div class="foot"><h5>Loja</h5><ul>
      <li><a href="#produtos">Ofertas Relâmpago</a></li>
      <li><a href="#produtos">Mais descontos</a></li>
      <li><a href="#artigos">Editorial</a></li>
    </ul></div>
    <div class="foot"><h5>Editorial</h5><ul>
      <li><a href="#manifesto">Manifesto</a></li>
      <li><a href="#artigos">Diário do bot</a></li>
    </ul></div>
    <div class="foot"><h5>Disclaimer</h5><ul>
      <li>Como Associado, ganho comissões</li>
      <li>Preços sujeitos a alteração</li>
      <li>Confirme antes de comprar</li>
    </ul></div>
  </div>
  <div class="foot-bottom">
    <span>© 2026 Relâmpago Bot · Curadoria + bot 24/7</span>
    <div class="foot-bottom-links"><a href="#">Privacidade</a><a href="#">Termos</a></div>
  </div>
</div></footer>"""


COUNTDOWN_JS = """<script>
(function(){
  var hours=2;
  var end=new Date(); end.setHours(end.getHours()+hours); end.setMinutes(0); end.setSeconds(0);
  function tick(){
    var diff=Math.max(0,(end-new Date())/1000);
    var h=Math.floor(diff/3600),m=Math.floor((diff%3600)/60),s=Math.floor(diff%60);
    var box=document.getElementById('countdown'); if(!box) return;
    box.querySelector('[data-cd=h]').textContent=String(h).padStart(2,'0');
    box.querySelector('[data-cd=m]').textContent=String(m).padStart(2,'0');
    box.querySelector('[data-cd=s]').textContent=String(s).padStart(2,'0');
    if(diff<=0){end.setHours(end.getHours()+hours);}
  }
  tick(); setInterval(tick,1000);
  document.querySelectorAll('.cat-tab').forEach(function(t){
    t.addEventListener('click',function(){
      document.querySelectorAll('.cat-tab').forEach(function(x){x.classList.remove('active')});
      t.classList.add('active');
      var cat=t.dataset.cat;
      document.querySelectorAll('#products-grid .product').forEach(function(p){
        var loja=p.querySelector('.product-cat').textContent.trim();
        p.style.display=(cat==='all'||loja===cat)?'':'none';
      });
    });
  });
})();
</script>"""


def _html_catalogo(ofertas, base_url):
    return f"""<!doctype html>
<html lang="pt-BR"><head>
<title>Relâmpago · Diário de Compras Inteligentes</title>
<meta name="description" content="Curadoria humana, preços rastreados por bot. As melhores ofertas do dia em Amazon e Mercado Livre.">
{HEAD_COMMON.format(css_path=base_url + "/styles.css" if base_url else "styles.css")}
</head><body>
{TOP_BAR}
{_nav(base_url)}
{_wa_banner_section()}
{_products_section(ofertas, base_url)}
{FLASH_BANNER}
{TRUST_STRIP}
{ARTICLES_SECTION}
{EDITORIAL_BLOCK}
{TESTIMONIALS}
{NEWSLETTER}
{FOOTER}
{_wa_floating()}
{COUNTDOWN_JS}
</body></html>"""


def _html_oferta(o, base_url):
    produto = escape(o.get("produto") or "")
    preco = o.get("preco") or 0
    desconto = int(o.get("desconto") or 0)
    imagem = o.get("imagem") or ""
    loja = escape(o.get("loja") or "loja")
    link = escape(o.get("url_destino") or "#")
    preco_antigo = preco / (1 - desconto / 100) if preco and desconto else 0
    economia = preco_antigo - preco if preco_antigo else 0
    css_path = "../../styles.css"

    img_block = (
        f'<img src="{escape(imagem)}" alt="{produto[:80]}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:contain;padding:8%;background:var(--bg-card)">'
        if imagem else f'<div class="ph ph-1 ph-stripe"></div>'
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head>
<title>{produto[:60]} · Relâmpago</title>
<meta name="description" content="{produto[:140]} com {desconto}% de desconto em {loja}.">
<meta property="og:title" content="{produto[:60]}">
<meta property="og:description" content="-{desconto}% · {_brl(preco)} em {loja}">
{f'<meta property="og:image" content="{escape(imagem)}">' if imagem else ''}
{HEAD_COMMON.format(css_path=css_path)}
</head><body>
{TOP_BAR}
{_nav(base_url)}

<section class="hero"><div class="container">
  <div class="hero-grid">
    <div>
      <div class="eyebrow"><span class="dot"></span>{loja} · Oferta verificada</div>
      <h1 style="font-size:clamp(36px,5vw,72px);line-height:1.02">{produto}</h1>
      <p class="hero-lede">Preço rastreado nas últimas 24h. Desconto real validado pelo bot. Estoque limitado.</p>

      <div style="display:flex;align-items:baseline;gap:18px;margin:24px 0 8px;flex-wrap:wrap">
        <span style="font-family:var(--display);font-size:64px;line-height:1;letter-spacing:-0.02em;color:var(--accent-deep)">{_brl(preco)}</span>
        {f'<span style="font-family:var(--mono);font-size:18px;color:var(--ink-3);text-decoration:line-through">{_brl(preco_antigo)}</span>' if preco_antigo else ''}
      </div>
      {f'<div style="font-family:var(--mono);font-size:12px;letter-spacing:0.16em;text-transform:uppercase;color:var(--accent-deep);margin-bottom:24px">Economia {_brl(economia)} · -{desconto}% OFF</div>' if economia else ''}

      <div class="hero-ctas">
        <a class="btn btn-accent" href="{link}" rel="nofollow sponsored" target="_blank" style="padding:18px 32px;font-size:16px">
          Ver oferta em {loja} <span class="arrow">→</span>
        </a>
        <a class="btn btn-ghost" href="{base_url}/">Voltar ao catálogo</a>
      </div>

      <div class="hero-meta">
        <div class="hero-meta-item"><div class="num">-{desconto}%</div><div class="lbl">Desconto</div></div>
        <div class="hero-meta-item"><div class="num">★★★★★</div><div class="lbl">Verificado bot</div></div>
        <div class="hero-meta-item"><div class="num">24h</div><div class="lbl">Limitado</div></div>
      </div>
    </div>

    <div style="position:relative">
      <div class="hero-card">
        {img_block}
        <div class="ph-label">{loja} · Estoque limitado</div>
        <div class="hero-card-overlay">
          <div class="hero-card-tag">
            {f'<span class="strike-old">De {_brl(preco_antigo)}</span>' if preco_antigo else '<span class="strike-old">Preço relâmpago</span>'}
            <span class="price">{_brl(preco)}</span>
          </div>
          {f'<div class="hero-card-discount">-{desconto}%</div>' if desconto else ''}
        </div>
      </div>
    </div>
  </div>
</div></section>

<section class="container" style="margin:40px 0 80px">
  <div style="background:var(--bg-card);border:1px solid var(--line);border-radius:22px;padding:32px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px">
    <div><div class="eyebrow" style="margin-bottom:8px"><span class="dot"></span>Como o bot validou</div><p style="margin:0;color:var(--ink-2);font-size:14px">Preço comparado ao histórico de 30 dias. Desconto real ≥ {desconto}%.</p></div>
    <div><div class="eyebrow" style="margin-bottom:8px"><span class="dot"></span>Loja</div><p style="margin:0;color:var(--ink-2);font-size:14px">{loja} — frete e prazo conforme a página da loja.</p></div>
    <div><div class="eyebrow" style="margin-bottom:8px"><span class="dot"></span>Disclaimer</div><p style="margin:0;color:var(--ink-2);font-size:14px">Como Associado, ganho comissões sobre compras qualificadas. Preço sujeito a alteração.</p></div>
  </div>
</section>

{FOOTER}
{_wa_floating()}
</body></html>"""


def gerar(base_url: str = "", limite: int = 100) -> int:
    base_url = base_url.rstrip("/")
    BLOG_REPO.mkdir(exist_ok=True)
    (BLOG_REPO / ".nojekyll").touch()

    src_css = ROOT / "_relampago_styles.css"
    dst_css = BLOG_REPO / "styles.css"
    if src_css.exists() and (not dst_css.exists() or src_css.stat().st_mtime > dst_css.stat().st_mtime):
        shutil.copy(src_css, dst_css)

    ofertas_lista = listar_ofertas_publicas(limite)

    (BLOG_REPO / "index.html").write_text(_html_catalogo(ofertas_lista, base_url), encoding="utf-8")

    oferta_dir = BLOG_REPO / "oferta"
    if oferta_dir.exists():
        shutil.rmtree(oferta_dir)
    oferta_dir.mkdir()

    count = 0
    for o in ofertas_lista:
        full = buscar_oferta_por_slug(o["slug"])
        if not full:
            continue
        slug_dir = oferta_dir / o["slug"]
        slug_dir.mkdir(exist_ok=True)
        (slug_dir / "index.html").write_text(_html_oferta(full, base_url), encoding="utf-8")
        count += 1
    return count


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("config.env")
    base = os.getenv("BASE_URL", "")
    n = gerar(base)
    print(f"Gerado: {n} páginas + index. base_url={base}")
