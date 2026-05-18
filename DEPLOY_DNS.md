# Deploy domínio `ofertasrelampagobot.com.br`

## Status atual (18/05/2026)
- Domínio registrado no registro.br
- Repo blog: `matheusmoraesnascimento-beep/ofertas-relampago-bot` (público)
- GitHub Pages com `CNAME=ofertasrelampagobot.com.br` configurado via API
- `BASE_URL=https://ofertasrelampagobot.com.br` no `config.env` do bot
- HTTPS ainda **não habilitado** (depende DNS propagar)

## 1. Configurar DNS no registro.br

Acesse: https://registro.br → Login → seu domínio → **DNS / Editar Zona**

Adicione esses registros:

| Tipo  | Nome | Valor                                      | TTL  |
|-------|------|--------------------------------------------|------|
| A     | @    | 185.199.108.153                            | 3600 |
| A     | @    | 185.199.109.153                            | 3600 |
| A     | @    | 185.199.110.153                            | 3600 |
| A     | @    | 185.199.111.153                            | 3600 |
| CNAME | www  | matheusmoraesnascimento-beep.github.io.    | 3600 |

> `@` significa apex (raiz do domínio). Em alguns painéis aparece como campo vazio ou `ofertasrelampagobot.com.br`.

Salva. Propagação ~15min a 2h.

## 2. Verificar propagação

```bash
# DNS resolveu?
dig +short ofertasrelampagobot.com.br
# Esperado: 185.199.108.153 (+ outros 3)

dig +short www.ofertasrelampagobot.com.br
# Esperado: matheusmoraesnascimento-beep.github.io. → IPs

# Site responde?
curl -I http://ofertasrelampagobot.com.br
# Esperado: 200 OK ou 301 redirect pra https
```

## 3. Ativar HTTPS (após DNS resolver)

GitHub provisiona Let's Encrypt automaticamente. Espere ~10min após DNS responder, então:

```bash
gh api -X PUT repos/matheusmoraesnascimento-beep/ofertas-relampago-bot/pages \
  --input - <<'EOF'
{"https_enforced":true}
EOF
```

Confirma:
```bash
gh api repos/matheusmoraesnascimento-beep/ofertas-relampago-bot/pages \
  --jq '{html_url,cname,https_enforced}'
# Esperado: {"html_url":"https://ofertasrelampagobot.com.br/","cname":"ofertasrelampagobot.com.br","https_enforced":true}

curl -I https://ofertasrelampagobot.com.br
# Esperado: HTTP/2 200
```

## 4. Atualizar bio Instagram

Quando HTTPS funcionar, troque a URL na bio do Instagram pra:
```
https://ofertasrelampagobot.com.br
```

## 5. Troubleshooting

**DNS não resolve depois de 2h:** registro.br pode demorar até 24h. Verifique se salvou no painel — alguns registradores exigem confirmar zona.

**Pages retorna 404 com DNS ok:** force rebuild:
```bash
cd ~/ofertas-relampago-bot
git commit --allow-empty -m "trigger rebuild" && git push
```

**Cert SSL não provisiona:** GitHub precisa que TODOS os 4 IPs A respondam corretamente. Confirme com `dig`. Se A records têm proxy (Cloudflare), desabilita proxy.

**Erro "CAA record":** registro.br não deveria ter CAA por padrão, mas se houver, adicione:
```
CAA 0 issue "letsencrypt.org"
```

## 6. Comandos úteis (de qualquer PC)

```bash
# Status Pages
gh api repos/matheusmoraesnascimento-beep/ofertas-relampago-bot/pages

# Logs último build
gh api repos/matheusmoraesnascimento-beep/ofertas-relampago-bot/pages/builds/latest

# Forçar rebuild
cd ~/ofertas-relampago-bot && git commit --allow-empty -m "rebuild" && git push
```
