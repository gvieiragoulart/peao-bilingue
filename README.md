# Peão Bilíngue

Radar pessoal de vagas: coleta em vários sites, filtra pelas suas buscas, analisa o encaixe de
cada vaga nova com um LLM e avisa por email (análise completa) e WhatsApp (resumo).

Para cada vaga nova a análise traz fit score, resumo do encaixe, passos de preparação,
exatamente 20 perguntas de entrevista, gaps e o que melhorar no seu perfil.

> **Em transição para app desktop Windows.** Hoje roda pela linha de comando. A interface
> CustomTkinter e o agendamento pelo Agendador do Windows vêm nas próximas fases (ver
> [CLAUDE.md](CLAUDE.md)).

## Instalação

```bash
uv sync
cp .env.example .env     # preencha o que for usar (chave de API, SMTP, Twilio)
```

O projeto usa o **Chrome instalado na máquina**, não o Chromium do Playwright: o Cloudflare da
VanHack recusa navegadores atípicos.

## Primeiro uso

**1. Login na VanHack (manual, sempre).** O login é sem senha (link por email, Google ou
LinkedIn) e protegido por verificação humana, então não existe login automático:

```bash
uv run peao login
```

Abre uma janela do Chrome. Se entrar por email, **copie o link recebido e cole na barra dessa
janela** — clicar pelo cliente de email cria a sessão no navegador errado. A verificação
"confirme que é humano" é sua; o robô nunca a resolve. Confira com `uv run peao check`.

**2. Cadastre as buscas:**

```bash
uv run peao buscas adicionar "Python" python django fastapi
uv run peao buscas adicionar "React" react typescript --exclude internship
uv run peao buscas                    # lista
```

Cuidado com `--exclude`: o filtro olha a descrição inteira, e vaga sênior costuma dizer
"mentor junior engineers" — excluir "junior" descartaria justamente essas.

**3. Rode:**

```bash
uv run peao run --sem-analise    # só coleta e salva; não chama LLM, não gasta crédito
uv run peao run --dry-run        # analisa, mas não notifica
uv run peao run                  # coleta, analisa e notifica
```

`--sem-analise` é o jeito de validar a coleta de graça. Para limitar fontes ou trocar o LLM:
`--fonte vanhack --llm anthropic`. `uv run peao adaptadores` lista o que está disponível.

## Como funciona

Arquitetura de portas e adaptadores: o núcleo só conhece interfaces (`FonteDeVagas`,
`ProvedorLLM`, `Notificador`, `RepositorioVagas`), e cada site, LLM ou canal é um adapter
registrado numa fábrica pelo nome. Adicionar uma fonte nova é escrever um módulo e registrá-lo
— nada no núcleo muda. Detalhes e decisões em [CLAUDE.md](CLAUDE.md).

Cada execução fica registrada com contadores e erros. Uma fonte com problema não derruba as
outras; qualquer falha de leitura deixa screenshot + HTML em `artifacts/`.

## Sessão expirada

Quando uma execução terminar com `login_required`, rode `uv run peao login` de novo. O
`data/state.json` contém cookies de sessão: trate como senha e nunca versione (já está no
`.gitignore`).

## Desenvolvimento

```bash
uv run pytest                         # todos offline: sem site, sem SMTP, sem LLM
uv run ruff check . && uv run ruff format .
```

O pipeline inteiro é testado com dublês das portas e um SQLite em memória. Os adapters de
scraping usam HTML real anonimizado em `tests/fixtures/<fonte>/`.
