# Monitoramento de Ferramentas - Instituto Cerrados

Painel de gestao das plataformas digitais de Yuri Salmona / Instituto Cerrados.

**Acesso restrito.** Desde 05/10/2026 o painel nao fica mais publico no GitHub
Pages: e servido por um app Streamlit com login Google, liberado apenas para os
e-mails listados em `EMAILS_AUTORIZADOS` no `app.py`.

- Painel (com login): ver a URL do app no Streamlit Community Cloud
- Agrupamento oficial: https://sistema-cerrado.streamlit.app/
- Identidade visual: https://plataforma-editais-ic.vercel.app/

Arquivo mestre de contexto: projetos-ic-contexto.md no Google Drive institucional.
Monitor automatico semanal ativo via Claude (segundas ~9h Brasilia).

## Como atualizar (nao mudou)

Peca em qualquer conversa do Claude: "atualize o painel de projetos" (skill
gestao-projetos-ic). O Claude gera o novo `index.html`; substitua o arquivo
neste repositorio (Upload files - Commit). O app le o `index.html` do
repositorio a cada carregamento, entao a atualizacao aparece sozinha.

## Como funciona

- `index.html` e `docs.html` sao o conteudo (gerados pela rotina) e seguem
  sendo a fonte da verdade.
- `app.py` so faz duas coisas: exige o login e serve esses arquivos. Ele junta
  as duas paginas num documento so e reescreve os links `docs.html#ancora`
  como ancoras internas, para o botao "Docs" de cada card continuar
  funcionando dentro do app.
- Para liberar o painel para outra pessoa do IC, acrescente o e-mail em
  `EMAILS_AUTORIZADOS` (`app.py`) e faca commit.

## Rodar localmente

```
pip install -r requirements.txt
streamlit run app.py
```

Sem `.streamlit/secrets.toml`, roda sem login (modo desenvolvimento).
