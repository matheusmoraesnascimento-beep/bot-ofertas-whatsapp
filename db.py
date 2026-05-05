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
                data_envio TEXT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_link ON ofertas_enviadas(link)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data ON ofertas_enviadas(data_envio)")
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


def salvar_oferta(oferta: dict):
    with _conn() as con:
        con.execute(
            """INSERT INTO ofertas_enviadas
               (produto, loja, preco, link, desconto, imagem, data_envio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                oferta.get("produto", ""),
                oferta.get("loja", ""),
                oferta.get("preco_atual"),
                oferta.get("link_afiliado", ""),
                oferta.get("desconto_percentual", 0),
                oferta.get("imagem", ""),
                datetime.now().isoformat(),
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
