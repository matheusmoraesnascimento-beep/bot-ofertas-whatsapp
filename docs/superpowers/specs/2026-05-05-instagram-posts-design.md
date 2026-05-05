# Instagram Posts Generator — Design Spec
Date: 2026-05-05

## Goal
Generate 3 Instagram posts (image + caption) daily from top discount offers in the bot's SQLite database. Files saved locally and visible in the web panel for manual posting.

## Architecture

Script isolado `instagram_posts.py`, sem acoplamento ao `bot.py`. Roda uma vez por dia às 08h via `schedule` lib (adicionado ao loop do bot) ou Railway cron.

## Data Source

- Tabela `ofertas` no SQLite (`ofertas.db`)
- Query: top 3 por `desconto_percentual` das últimas 24h
- Filtro: sem produto duplicado (distinct por `produto`)
- Campos usados: `produto`, `preco_atual`, `preco_antigo`, `desconto_percentual`, `loja`, `imagem`, `link_afiliado`

## Output

```
posts/
  YYYY-MM-DD/
    post_1.jpg
    post_1.txt
    post_2.jpg
    post_2.txt
    post_3.jpg
    post_3.txt
```

## Image Generation (Pillow)

Dimensão: 1080x1080px

Layout:
- Fundo branco
- Foto do produto: baixada via URL campo `imagem`, redimensionada para caber em 1080x648 (60% altura), centralizada horizontalmente
- Badge vermelho canto superior direito: `-{desconto}%` (font bold, branco)
- Preço antigo riscado + preço atual em destaque (font grande, preto/vermelho)
- Rodapé cinza claro: nome da loja + "Comenta QUERO que mando o link 🔥"

Fallback: se download da imagem falhar, usa fundo colorido sólido com nome do produto em texto.

## Caption Template

```
{nome_curto} 🔥

De ~~R${preco_antigo}~~ por R${preco_atual} (-{desconto}%)
📍 {loja}

Comenta QUERO que mando o link no direct 👇

#oferta #promocao #{loja_hashtag} #ofertas #desconto
```

`nome_curto`: primeiros 60 chars do nome do produto.

## Scheduling

Adiciona ao loop principal do `bot.py` via `schedule` lib:
```python
schedule.every().day.at("08:00").do(gerar_posts_instagram)
```

## Web Panel — Nova Aba

- Aba "Posts Instagram" no painel Flask (`painel/`)
- Lista posts do dia em grade (3 cards)
- Cada card: preview da imagem + textarea com caption + botão "Baixar imagem"
- Rota Flask: `GET /instagram-posts` — retorna posts do dia

## Dependencies

- `Pillow` (já pode estar, verificar requirements.txt)
- `requests` / `curl_cffi` para download de imagem do produto
- `schedule` (já usado no bot)

## Error Handling

- Sem ofertas nas últimas 24h: loga warning, não gera arquivos
- Download imagem falha: usa fallback fundo colorido
- Escrita disco falha: loga erro, não quebra o bot

## Out of Scope

- Posting automático via API Instagram
- Edição de imagem pelo painel
- Agendamento configurável pelo painel
