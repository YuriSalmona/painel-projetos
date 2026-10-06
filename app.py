# -*- coding: utf-8 -*-
"""Monitoramento de Ferramentas — Instituto Cerrados (acesso restrito).

Este app existe para pôr o painel atrás de login. O conteúdo continua sendo
o `index.html` (e o `docs.html`) gerados pela rotina de gestão de projetos:
este arquivo apenas autentica e serve o HTML já existente. Para atualizar o
painel, siga substituindo o `index.html` como sempre — nada aqui muda.

Login Google restrito aos e-mails de EMAILS_AUTORIZADOS, exigido quando o
bloco [auth] existe nos secrets (produção). Em dev local, sem esse bloco,
roda sem login.
"""

import pathlib
import re

import streamlit as st

st.set_page_config(
    page_title="Monitoramento de Ferramentas — Instituto Cerrados",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Quem pode abrir o painel. Para liberar para mais alguém do IC, acrescente
# o e-mail aqui (ex.: a diretoria de operações) e publique.
EMAILS_AUTORIZADOS = {"yuri@cerrados.org"}

BASE = pathlib.Path(__file__).parent


def _auth_configurado():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def _gate_de_login():
    """Mesmo padrão dos demais apps do IC: botão de login Google e, depois,
    conferência do e-mail. Sem o bloco [auth] nos secrets (dev local), passa
    direto para facilitar o desenvolvimento."""
    if not _auth_configurado():
        return
    if not st.user.is_logged_in:
        st.title("Monitoramento de Ferramentas")
        st.caption("Instituto Cerrados")
        st.info("Painel interno. Entre com sua conta Google institucional.")
        st.button("Entrar com Google", on_click=st.login, type="primary")
        st.stop()
    email = (st.user.email or "").strip().lower()
    if email not in EMAILS_AUTORIZADOS:
        st.error(
            f"Este painel é restrito. A conta {st.user.email} não tem acesso."
        )
        st.button("Sair", on_click=st.logout)
        st.stop()
    st.sidebar.caption(f"Logado como {st.user.email}")
    st.sidebar.button("Sair", on_click=st.logout)


# --- Montagem do documento ------------------------------------------------
# O painel e a documentação técnica são dois arquivos que se linkam por
# `docs.html#ancora` (o botão "Docs" de cada card). Dentro do iframe do
# Streamlit não existe navegação entre arquivos, então juntamos os dois num
# documento só e reescrevemos esses links como âncoras internas — assim o
# botão "Docs" continua funcionando exatamente como no site publicado.

_RE_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.S | re.I)
_RE_BODY = re.compile(r"<body[^>]*>(.*?)</body>", re.S | re.I)


def _trechos(html):
    """Devolve (estilos, conteúdo do body) de um documento HTML completo."""
    estilos = "\n".join(_RE_STYLE.findall(html))
    m = _RE_BODY.search(html)
    corpo = m.group(1) if m else html
    return estilos, corpo


@st.cache_data(show_spinner=False)
def _documento(assinatura):
    """Documento único: painel + documentação técnica. `assinatura` (tamanho
    e data dos arquivos) entra só para o cache expirar sozinho quando a
    rotina semanal substituir o index.html."""
    index = (BASE / "index.html").read_text(encoding="utf-8")
    # Resultado do verificador automático (scripts/verificar.py, a cada 4 h).
    # Dentro do iframe o painel não consegue buscar o status.json, então ele
    # vai embutido no documento.
    status_path = BASE / "status.json"
    if status_path.exists():
        dados = status_path.read_text(encoding="utf-8").replace("</", "<\\/")
        embutido = "<script>window.STATUS_IC=" + dados + ";</script>\n<script>"
        index = index.replace("<script>", embutido, 1)
    docs_path = BASE / "docs.html"
    if docs_path.exists():
        estilos_docs, corpo_docs = _trechos(docs_path.read_text(encoding="utf-8"))
        bloco = f'{estilos_docs}<div id="documentacao-tecnica">{corpo_docs}</div>'
        if "</body>" in index:
            index = index.replace("</body>", bloco + "</body>")
        else:
            index += bloco
        # "docs.html#x" -> "#x" (e o link "voltar ao painel" do docs.html)
        index = re.sub(r'href="docs\.html#', 'href="#', index)
        index = re.sub(r'href="docs\.html"', 'href="#documentacao-tecnica"', index)
        index = re.sub(r'href="index\.html"', 'href="#"', index)

    # O iframe ocupa a altura da JANELA (não a do conteúdo) e o conteúdo rola
    # dentro dele. Isso é de propósito: o painel tem barra lateral fixa com
    # `height:100vh`, e dentro de um iframe o "vh" é a altura do iframe — com
    # altura automática, cada ajuste aumentaria o conteúdo e o ajuste seguinte
    # cresceria de novo, sem parar (chegou a 160 mil px no teste). Preso à
    # janela, o `100vh` volta a significar o mesmo que no site publicado.
    ajuste_altura = """
<script>
(function () {
  function ajustar() {
    try {
      var alvo = window.frameElement;
      if (!alvo || !window.parent) return;
      var h = window.parent.innerHeight;
      if (!h) return;
      alvo.style.height = Math.max(h - 6, 420) + 'px';
    } catch (e) { /* origem diferente: fica o height fixo */ }
  }
  window.addEventListener('load', ajustar);
  window.addEventListener('resize', ajustar);
  try { window.parent.addEventListener('resize', ajustar); } catch (e) {}
  ajustar();
  setTimeout(ajustar, 300);
})();
</script>
"""
    if "</body>" in index:
        index = index.replace("</body>", ajuste_altura + "</body>")
    else:
        index += ajuste_altura
    return index


def _assinatura_arquivos():
    partes = []
    for nome in ("index.html", "docs.html", "status.json"):
        p = BASE / nome
        if p.exists():
            s = p.stat()
            partes.append(f"{nome}:{s.st_size}:{int(s.st_mtime)}")
    return "|".join(partes)


_gate_de_login()

# Tira as margens do Streamlit: o HTML do painel já traz o seu próprio
# layout e deve ocupar a largura toda.
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], footer, #MainMenu { visibility: hidden; height: 0; }
      .block-container { padding: 0 !important; max-width: 100% !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# height é só o valor inicial/reserva: o script dentro do documento ajusta o
# iframe à altura da janela assim que carrega.
st.components.v1.html(_documento(_assinatura_arquivos()), height=900, scrolling=True)
