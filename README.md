# Peão Bilíngue

Radar pessoal de vagas: coleta em vários sites, filtra pelas suas buscas e avisa das vagas
novas por email e WhatsApp. Você escolhe quais analisar, com qual LLM e com o perfil de qual
fonte.

A análise traz fit score, resumo do encaixe, passos de preparação, exatamente 20 perguntas de
entrevista, gaps e o que melhorar no seu perfil.

## Instalação

```bash
uv sync
uv run peao-ui
```

O app abre direto, sem console. Rode sempre na pasta do projeto: os dados (`data/`) e o `.env`
são procurados na pasta atual. Tudo se configura pelas abas — fontes, buscas, provedores de
LLM, avisos e limites. **Chaves e senhas ficam no Cofre de Credenciais do Windows**, não em
arquivo; o resto vai para `data/config.json`. O `.env` (copiado de `.env.example`) continua
funcionando como alternativa para quem prefere a linha de comando.

| Aba | Para quê |
|---|---|
| Vagas | lista com fit e filtros; escolha o LLM e o perfil e clique em **Analisar**; marcar como estudando/aplicada/descartada |
| Buscas | palavras-chave, termos excluídos e quais fontes cada busca usa |
| Fontes | liga/desliga cada site; login manual e verificação de sessão |
| LLMs | o LLM que já vem escolhido na aba Vagas, modelos e chaves |
| Perfil | o perfil de cada fonte (sem dados pessoais) e o histórico de mudanças dele |
| Execuções | "Coletar agora", coleta diária automática, histórico e o registro ao vivo |
| Configurações | limites da coleta e canais de aviso das vagas novas (email, WhatsApp) |

**Cada fonte tem o seu perfil** — o cadastrado na VanHack não é o do LinkedIn — e a análise de
uma vaga usa, por padrão, o perfil da fonte dela. A coleta não chama LLM: nada é gasto até você
clicar em Analisar.

**Fontes disponíveis:** VanHack (login manual, lê o seu perfil), Remotive e Remote OK (APIs
públicas de vagas remotas, sem conta), Arbeitnow (vagas na Alemanha com patrocínio de visto),
Himalayas (vagas remotas abertas a quem está no Brasil) e We Work Remotely (feed RSS público). As APIs são consultadas uma vez por coleta, e a resposta
é reaproveitada por 6 horas — o Remotive pede no máximo ~4 consultas por dia. Cada vaga mantém
o link original na fonte, como os termos delas pedem. Ligue as fontes na aba Fontes, ou só
para uma coleta: `uv run peao run --fonte remoteok`.

O projeto usa o **Chrome instalado na máquina**, não o Chromium do Playwright: o Cloudflare da
VanHack recusa navegadores atípicos.

## Pela linha de comando

A CLI faz login, buscas, coleta e agendamento — é ela que a coleta agendada usa. A análise fica
no app.

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

**3. Colete:**

```bash
uv run peao run                  # coleta e salva as vagas novas; não chama LLM
uv run peao run --avisar         # e manda o resumo das vagas novas pelos canais ligados
```

Para limitar as fontes: `--fonte vanhack`. `uv run peao adaptadores` lista o que está
disponível.

## Coleta diária automática

Na aba **Execuções**, digite o horário e clique em **Agendar** — ou pela linha de comando:

```bash
uv run peao agenda ativar --horario 08:00
uv run peao agenda                    # próxima e última execução
uv run peao agenda desativar
```

A tarefa fica no Agendador de Tarefas do Windows ("Peao Bilingue - coleta diaria") e roda com o
app fechado; se o PC estiver desligado na hora marcada, ela roda assim que ele ligar. Coleta
como o `uv run peao run` e **avisa das vagas novas** (título, fonte e link) pelos canais ligados
em Configurações — eles começam desligados; ligue os que já tiver preenchido. Como roda sem
janela, o registro fica em `data/coleta.log`. Só uma coleta roda por vez: se a tarefa começar
enquanto você coleta pelo app (ou o contrário), a segunda é recusada.

## Escolhendo o LLM

Quatro provedores: **Claude** (`anthropic`, padrão), **Ollama** (local e grátis), **OpenAI** e
**Gemini**. A escolha é feita na aba Vagas, a cada análise; o último escolhido vira o padrão.

Para não gastar nada, instale o Ollama e baixe um modelo que caiba numa GPU de 6 GB:

```bash
ollama pull qwen3:8b
```

Modelos locais de 7–8B são mais fracos na análise fina (as 20 perguntas e as melhorias de
perfil): bons para uma primeira olhada, e o Claude para as vagas que interessarem de verdade.

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
uv run pytest -m "not integracao"     # só unidade: segundos
uv run pytest -m integracao           # Chromium, janela Tk, PowerShell, outro processo
uv run ruff check . && uv run ruff format .
uv run mypy                           # tipagem estrita do código em src/
```

O pipeline inteiro é testado com dublês das portas e um SQLite em memória. Os adapters de
scraping usam HTML real anonimizado em `tests/fixtures/<fonte>/`.

**CI** (`.github/workflows/ci.yml`): todo PR e todo push na `main` rodam três jobs — lint e
tipagem (ruff e mypy, no Linux), testes de unidade e testes de integração (no Windows, o SO do
app; o de integração instala o Chromium do Playwright, com cache).
