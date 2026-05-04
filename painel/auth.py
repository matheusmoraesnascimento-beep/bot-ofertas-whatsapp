import os
from functools import wraps
from flask import session, redirect, url_for

SENHA = os.getenv("PAINEL_SENHA", "admin123")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def verificar_senha(senha: str) -> bool:
    return senha == SENHA
