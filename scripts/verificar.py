"""Verificador das ferramentas do Instituto Cerrados.

Roda no GitHub Actions a cada 4 horas (.github/workflows/verificar.yml).
Lê ferramentas.json, testa cada ferramenta, grava status.json (que o painel
mostra) e acrescenta uma linha por ferramenta em historico.csv.

Quando há GITHUB_TOKEN e GITHUB_REPOSITORY no ambiente, também abre uma
issue "[fora do ar] <nome>" para cada ferramenta com problema e fecha a issue
quando a ferramenta volta. A issue é o alerta: o GitHub manda e-mail ao dono
do repositório.

Só usa a biblioteca padrão do Python, para não depender de instalação.

Status possíveis:
  ok              no ar
  atencao         responde, mas algo está fora do normal (ex.: app dormindo)
  fora            não responde ou responde com erro
  nao_verificavel o host não deixa verificar de fora (ex.: app privado)
"""

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (monitor-ferramentas-ic; +https://yurisalmona.github.io/painel-projetos/)"
TIMEOUT = 45

# Códigos do endpoint /api/v2/app/status do Streamlit Community Cloud,
# observados em 05/10/2026: 5 = rodando, 10 = erro ao iniciar (ex.: o host
# não consegue clonar o repositório). Os demais aparecem com o app dormindo
# ou subindo; tratamos como "atenção" e registramos o código.
STREAMLIT_RODANDO = 5
STREAMLIT_ERRO = 10


def baixar(url, limite=200_000):
    """Devolve (código HTTP, corpo). Não levanta exceção para 4xx/5xx."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(limite).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read(limite).decode("utf-8", "ignore")
        except Exception:
            corpo = ""
        return e.code, corpo


def checar_streamlit(f):
    base = f["url"].rstrip("/")
    codigo, corpo = baixar(base + "/api/v2/app/status")
    if codigo == 200:
        try:
            st = json.loads(corpo).get("status")
        except ValueError:
            st = None
        if st == STREAMLIT_RODANDO:
            return "ok", "Rodando"
        if st == STREAMLIT_ERRO:
            return "fora", ("Erro ao iniciar (\"Oh no. Error running app\"). Abra Manage app "
                            "e veja o log; se aparecer \"Failed to download the sources\", "
                            "o Streamlit perdeu acesso ao repositório.")
        return "atencao", f"App dormindo ou reiniciando (código Streamlit {st}). Quem abrir verá a tela de acordar."
    if codigo == 404 and f.get("privado"):
        return "nao_verificavel", "App privado no Streamlit: o status só aparece para quem tem acesso."
    # Plano B: endpoint de saúde do próprio Streamlit.
    codigo2, corpo2 = baixar(base + "/~/+/_stcore/health")
    if codigo2 == 200 and corpo2.strip() == "ok":
        return "ok", "Rodando (verificado pelo endpoint de saúde)"
    return "fora", f"Status indisponível (HTTP {codigo} / saúde HTTP {codigo2})."


def checar_web(f):
    codigo, corpo = baixar(f["url"])
    # A Vercel às vezes responde 307 com a página no corpo: conta como no ar.
    if codigo >= 400 or codigo == 0:
        return "fora", f"HTTP {codigo}"
    trecho = f.get("contem")
    if trecho and trecho.lower() not in corpo.lower():
        return "atencao", f"Página abriu (HTTP {codigo}), mas sem o texto esperado \"{trecho}\"."
    return "ok", f"HTTP {codigo}"


def checar_health(f):
    codigo, corpo = baixar(f["url"])
    if codigo == 200 and re.search(r'"ok"\s*:\s*true|^ok$', corpo.strip(), re.I):
        return "ok", "Serviço respondeu ok"
    return "fora", f"HTTP {codigo}: {corpo[:120]}"


CHECADORES = {"streamlit": checar_streamlit, "web": checar_web, "health": checar_health}


def checar(f):
    """Testa a ferramenta; se falhar, tenta de novo uma vez (evita alarme por soluço de rede)."""
    for tentativa in (1, 2):
        inicio = time.time()
        try:
            status, detalhe = CHECADORES[f["tipo"]](f)
        except Exception as e:  # timeout, DNS, TLS...
            status, detalhe = "fora", f"Sem resposta: {type(e).__name__}: {e}"[:200]
        ms = int((time.time() - inicio) * 1000)
        if status in ("ok", "nao_verificavel") or tentativa == 2:
            return {"status": status, "detalhe": detalhe, "ms": ms}
        time.sleep(20)


# ---------------------------------------------------------------- alertas
def api_github(metodo, caminho, dados=None):
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    url = f"https://api.github.com/repos/{repo}{caminho}"
    corpo = json.dumps(dados).encode() if dados is not None else None
    req = urllib.request.Request(url, data=corpo, method=metodo, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def sincronizar_issues(resultados):
    if not (os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        print("(sem GITHUB_TOKEN: alertas por issue desligados)")
        return
    abertas = api_github("GET", "/issues?state=open&labels=fora-do-ar&per_page=100")
    por_titulo = {i["title"]: i for i in abertas}
    for r in resultados:
        titulo = f"[fora do ar] {r['nome']}"
        issue = por_titulo.get(titulo)
        if r["status"] == "fora" and not issue:
            api_github("POST", "/issues", {
                "title": titulo,
                "labels": ["fora-do-ar"],
                "body": (f"O verificador automático encontrou **{r['nome']}** com problema.\n\n"
                         f"- Endereço: {r['url']}\n- Detalhe: {r['detalhe']}\n"
                         f"- Verificado em: {r['verificado_em']} (UTC)\n\n"
                         "Esta issue fecha sozinha quando a ferramenta voltar."),
            })
            print(f"  alerta aberto: {titulo}")
        elif r["status"] == "ok" and issue:
            api_github("POST", f"/issues/{issue['number']}/comments",
                       {"body": f"Voltou ao ar em {r['verificado_em']} (UTC). Fechando."})
            api_github("PATCH", f"/issues/{issue['number']}", {"state": "closed"})
            print(f"  alerta fechado: {titulo}")


def main():
    lista = json.loads((RAIZ / "ferramentas.json").read_text(encoding="utf-8"))["ferramentas"]
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resultados = []
    for f in lista:
        r = checar(f)
        r.update({"id": f["id"], "nome": f["nome"], "url": f["url"], "verificado_em": agora})
        resultados.append(r)
        print(f"{r['status']:16} {f['id']:32} {r['detalhe']}")

    (RAIZ / "status.json").write_text(json.dumps(
        {"verificado_em": agora, "ferramentas": resultados}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    hist = RAIZ / "historico.csv"
    novo = not hist.exists()
    with hist.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if novo:
            w.writerow(["verificado_em", "id", "status", "ms"])
        for r in resultados:
            w.writerow([agora, r["id"], r["status"], r["ms"]])

    sincronizar_issues(resultados)
    # Sai com sucesso mesmo com ferramenta fora: o alerta é a issue, não um
    # workflow vermelho (que pararia de registrar o histórico).
    return 0


if __name__ == "__main__":
    sys.exit(main())
