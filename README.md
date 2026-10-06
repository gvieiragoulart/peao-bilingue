# Peão Bilíngue

Radar pessoal de vagas: coleta em vários sites, filtra pelas suas buscas, analisa o encaixe de
cada vaga nova com um LLM e avisa por email (análise completa) e WhatsApp (resumo).

Para cada vaga nova a análise traz fit score, resumo do encaixe, passos de preparação,
exatamente 20 perguntas de entrevista, gaps e o que melhorar no seu perfil.

## Instalação

```bash
uv sync
uv run peao-ui
```

O app abre direto, sem console. Tudo se configura pelas abas — fontes, buscas, provedores de
LLM, avisos e limites. **Chaves e senhas ficam no Cofre de Credenciais do Windows**, não em
arquivo; o resto vai para `data/config.json`. O `.env` (copiado de `.env.example`) continua
funcionando como alternativa para quem prefere a linha de comando.

| Aba | Para quê |
|---|---|
| Vagas | lista com fit e triagem, filtros, análise completa, marcar como estudando/aplicada/descartada |
| Buscas | palavras-chave, termos excluídos e quais fontes cada busca usa |
| Fontes | liga/desliga cada site; login manual e verificação de sessão |
| LLMs | quem analisa, quem faz a triagem, modelos e chaves |
| Perfil | o perfil usado nas análises (sem dados pessoais) e o histórico de mudanças |
| Execuções | "Coletar agora", histórico e o registro ao vivo |
| Configurações | limites da coleta e canais de aviso (email, WhatsApp) |

O projeto usa o **Chrome instalado na máquina**, não o Chromium do Playwright: o Cloudflare da
VanHack recusa navegadores atípicos.

## Pela linha de comando

Tudo que a interface faz também existe na CLI — é ela que a coleta agendada usa.

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

## Escolhendo o LLM

Quatro provedores: **Claude** (`anthropic`, padrão), **Ollama** (local e grátis), **OpenAI** e
**Gemini**. Escolha com `LLM_ANALISE` no `.env` ou `--llm` na linha de comando.

Para gastar menos, use um modelo local na **triagem**: ele dá uma nota rápida a cada vaga nova,
e só as que passam de `LIMIAR_TRIAGEM` vão para a análise completa no provedor pago.

```bash
ollama pull qwen3:8b                                  # uma vez; cabe numa GPU de 6 GB
uv run peao run --dry-run --llm ollama                # tudo local
uv run peao run --triagem ollama --llm anthropic      # Ollama filtra, Claude analisa
```

Modelos locais de 7–8B são mais fracos na análise fina (as 20 perguntas e as melhorias de
perfil); para triagem eles servem bem.

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
