import sqlite3
import os
from datetime import datetime, timedelta

DB_FILE = os.getenv("DB_FILE", "ofertas.db")


def _conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ofertas_enviadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto TEXT,
                loja TEXT,
                preco REAL,
                link TEXT,
                desconto REAL,
                imagem TEXT,
                data_envio TEXT,
                titulo_norm TEXT
            )
        """)
        cols = {r[1] for r in con.execute("PRAGMA table_info(ofertas_enviadas)").fetchall()}
        if "titulo_norm" not in cols:
            con.execute("ALTER TABLE ofertas_enviadas ADD COLUMN titulo_norm TEXT")
        con.execute("CREATE INDEX IF NOT EXISTS idx_link ON ofertas_enviadas(link)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data ON ofertas_enviadas(data_envio)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_titulo_norm ON ofertas_enviadas(titulo_norm)")
        con.execute("""
            CREATE TABLE IF NOT EXISTS historico_precos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL,
                produto TEXT,
                loja TEXT,
                preco REAL NOT NULL,
                data TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_hp_link ON historico_precos(link)")
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


def ja_enviado(link: str, horas: int = 24) -> bool:
    limite = (datetime.now() - timedelta(hours=horas)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM ofertas_enviadas WHERE link = ? AND data_envio > ? LIMIT 1",
            (link, limite),
        ).fetchone()
    return row is not None


def ja_enviado_titulo(titulo_norm: str, horas: int = 48) -> bool:
    if not titulo_norm:
        return False
    limite = (datetime.now() - timedelta(hours=horas)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM ofertas_enviadas WHERE titulo_norm = ? AND data_envio > ? LIMIT 1",
            (titulo_norm, limite),
        ).fetchone()
    return row is not None


def salvar_oferta(oferta: dict):
    with _conn() as con:
        con.execute(
            """INSERT INTO ofertas_enviadas
               (produto, loja, preco, link, desconto, imagem, data_envio, titulo_norm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                oferta.get("produto", ""),
                oferta.get("loja", ""),
                oferta.get("preco_atual"),
                oferta.get("link_afiliado", ""),
                oferta.get("desconto_percentual", 0),
                oferta.get("imagem", ""),
                datetime.now().isoformat(),
                oferta.get("_titulo_norm", ""),
            ),
        )
        con.commit()


def listar_ofertas(limit: int = 200) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT produto, loja, preco, link, desconto, imagem, data_envio
               FROM ofertas_enviadas ORDER BY data_envio DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    cols = ["produto", "loja", "preco", "link", "desconto", "imagem", "data_envio"]
    return [dict(zip(cols, r)) for r in rows]


def migrar_csv(csv_path: str = "ofertas_enviadas.csv"):
    import csv as _csv
    if not os.path.exists(csv_path):
        return
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    with _conn() as con:
        for r in rows:
            con.execute(
                """INSERT OR IGNORE INTO ofertas_enviadas
                   (produto, loja, preco, link, data_envio)
                   VALUES (?, ?, ?, ?, ?)""",
                (r.get("produto"), r.get("loja"), r.get("preco"),
                 r.get("link"), r.get("data_envio")),
            )
        con.commit()
    print(f"Migrados {len(rows)} registros do CSV")


def registrar_preco(oferta: dict):
    with _conn() as con:
        con.execute(
            "INSERT INTO historico_precos (link, produto, loja, preco, data) VALUES (?,?,?,?,?)",
            (oferta["link_afiliado"], oferta.get("produto"), oferta.get("loja"),
             oferta["preco_atual"], datetime.now().isoformat()),
        )
        con.commit()


def preco_minimo_historico(link: str, dias: int = 30) -> float | None:
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT MIN(preco) FROM historico_precos WHERE link = ? AND data > ?",
            (link, limite),
        ).fetchone()
    return row[0] if row and row[0] is not None else None


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


def _slug_from(produto: str, loja: str) -> str:
    import re, unicodedata
    texto = f"{produto}-{loja}".lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:60]


def listar_ofertas_publicas(limit: int = 50) -> list[dict]:
    """Deriva ofertas do ofertas_enviadas + slug computado. Só ofertas com imagem real."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT produto, loja, preco, link, desconto, imagem, data_envio
            FROM ofertas_enviadas
            WHERE produto IS NOT NULL AND produto != ''
              AND imagem LIKE 'http%'
            GROUP BY produto
            ORDER BY data_envio DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    out = []
    for produto, loja, preco, link, desconto, imagem, data_envio in rows:
        slug = _slug_from(produto or "", loja or "")
        if not slug:
            continue
        out.append({
            "slug": slug,
            "produto": produto,
            "loja": loja or "",
            "preco": preco,
            "desconto": desconto,
            "imagem": imagem or "",
            "data_envio": data_envio,
            "url_destino": link,
        })
    return out


def buscar_oferta_por_slug(slug: str) -> dict | None:
    """Tenta match exato (link table) primeiro, depois reconstrói via slug computado."""
    with _conn() as con:
        row = con.execute(
            """
            SELECT l.url_destino, o.produto, o.preco, o.desconto, o.imagem, o.loja, o.data_envio
            FROM links l
            LEFT JOIN ofertas_enviadas o ON o.link = l.url_destino
            WHERE l.slug = ?
            ORDER BY o.data_envio DESC
            LIMIT 1
            """,
            (slug,),
        ).fetchone()
        if row and row[1]:
            return {
                "slug": slug, "url_destino": row[0], "produto": row[1] or "",
                "preco": row[2], "desconto": row[3], "imagem": row[4] or "",
                "loja": row[5] or "", "data_envio": row[6], "criado_em": None,
            }

        rows = con.execute(
            """
            SELECT produto, loja, preco, link, desconto, imagem, data_envio
            FROM ofertas_enviadas
            WHERE produto IS NOT NULL AND produto != ''
            ORDER BY data_envio DESC
            LIMIT 500
            """
        ).fetchall()
    for produto, loja, preco, link, desconto, imagem, data_envio in rows:
        if _slug_from(produto or "", loja or "") == slug:
            return {
                "slug": slug, "url_destino": link, "produto": produto,
                "loja": loja or "", "preco": preco, "desconto": desconto,
                "imagem": imagem or "", "data_envio": data_envio, "criado_em": None,
            }
    return None


def _buscar_oferta_por_slug_OLD(slug: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT l.slug, l.url_destino, l.produto, l.criado_em,
                   o.preco, o.desconto, o.imagem, o.loja, o.data_envio
            FROM links l
            LEFT JOIN ofertas_enviadas o ON o.link = l.url_destino
            WHERE l.slug = ?
            ORDER BY o.data_envio DESC
            LIMIT 1
            """,
            (slug,),
        ).fetchone()
    if not row:
        return None
    return {
        "slug": row[0],
        "url_destino": row[1],
        "produto": row[2] or "",
        "criado_em": row[3],
        "preco": row[4],
        "desconto": row[5],
        "imagem": row[6] or "",
        "loja": row[7] or "",
        "data_envio": row[8],
    }


def listar_links_com_stats() -> list[dict]:
    limite_24h = (datetime.now() - timedelta(hours=24)).isoformat()
    with _conn() as con:
        rows = con.execute(
            """
            SELECT
                l.slug, l.url_destino, l.produto, l.criado_em,
                COUNT(c.id) AS total_cliques,
                (
                    SELECT strftime('%H', c2.clicado_em)
                    FROM link_cliques c2
                    WHERE c2.slug = l.slug AND c2.clicado_em > ?
                    GROUP BY strftime('%H', c2.clicado_em)
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS hora_pico_raw
            FROM links l
            LEFT JOIN link_cliques c ON c.slug = l.slug
            GROUP BY l.slug
            ORDER BY l.criado_em DESC
            """,
            (limite_24h,),
        ).fetchall()
    return [
        {
            "slug": row[0],
            "url_destino": row[1],
            "produto": row[2] or "",
            "criado_em": row[3],
            "total_cliques": row[4],
            "hora_pico": f"{int(row[5])}h-{int(row[5])+1}h" if row[5] else None,
        }
        for row in rows
    ]


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
