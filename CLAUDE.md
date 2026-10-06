# Peão Bilíngue

Radar pessoal de vagas para o Gabriel: coleta vagas em vários sites, filtra por buscas
configuráveis, analisa o encaixe de cada vaga nova com um LLM e avisa por email e WhatsApp.
Vira app desktop Windows (CustomTkinter), com a coleta diária disparada pelo Agendador do Windows.

Para cada vaga nova a análise traz: fit score (0–100), resumo do encaixe, passos de preparação,
**exatamente 20** perguntas de entrevista, gaps e o que melhorar no perfil (CV, LinkedIn, VanHack).

## Contexto

- **Usuário:** Gabriel, engenheiro sênior backend (PHP/Laravel, Python, TypeScript, AWS). Usa
  **Windows** (PowerShell). Converse e escreva mensagens/commits em **português do Brasil**.
- **Histórico:** nasceu como "VanHack Watcher" (só VanHack, só Claude, painel FastAPI). Em
  2026-10-06 virou multi-fonte e multi-LLM com portas e adaptadores. O plano aprovado está em
  `~/.claude/plans/quero-alterar-o-nosso-resilient-patterson.md`.
- **Repositório:** `gvieiragoulart/peao-bilingue` (privado). O `gh` está instalado mas **fora do
  PATH** (`"/c/Program Files/GitHub CLI/gh.exe"`) e o PAT não tem escopo para criar repositório
  nem mudar visibilidade.
- **Hardware:** RTX 3050 Laptop com 6 GB de VRAM — limita o Ollama a modelos de 7–8B quantizados.

## Estado atual (2026-10-06)

**Fase 1 do novo roteiro concluída:** núcleo hexagonal, 105 testes offline, `ruff` limpo.
FastAPI, uvicorn e APScheduler saíram. Banco novo em `data/peao.db` (o antigo `watcher.db` ficou
intocado). Três buscas cadastradas: Python, PHP/Laravel, React/TypeScript — sem `exclude`, porque
filtrar "junior" descartaria vaga sênior que diz "mentor junior engineers".

---

## Regras inegociáveis

- **Não contornar 2FA, captcha nem detecção de bot, em nenhuma fonte.** Nada de stealth,
  falsificação de fingerprint ou rotação de IP. Se aparecer: parar, salvar evidência
  (`artifacts/`), avisar o usuário e exigir login manual.
- **Login é sempre manual** nas fontes que exigem conta. O robô só reaproveita a sessão salva; se
  expirou, a execução termina com `login_required`. Nunca preencher formulário de login.
- **Comportamento educado:** uma execução por vez, sem páginas em paralelo, pausa aleatória de
  2–5 s entre navegações (é responsabilidade do adapter), limite de vagas detalhadas por execução.
- **Fontes com API ou feed oficial** usam a API/feed. Scraping só onde não houver alternativa, e
  sempre lendo o DOM como um usuário.
- **VanHack:** nada de chamar a API interna (nem httpx, nem interceptando XHR).
- **Segredos fora do código:** hoje no `.env` (no `.gitignore`, junto com `data/` e `artifacts/`);
  na Fase 3 passam para o Cofre de Credenciais do Windows via `keyring`. Nunca logar senha nem
  cookie.
- **PII fora do snapshot e do prompt:** nada de email, telefone, documento, visto, passaporte,
  cidadania, nome, nem URLs assinadas (currículo, vídeo). Há teste travando isso.
- Todo texto voltado ao usuário em **português do Brasil**.

---

## Arquitetura: portas e adaptadores

```
src/peao_bilingue/
├── dominio/
│   ├── entidades.py   # VagaResumo, Vaga, Perfil, JobAnalysis, Busca, Execucao (pydantic, sem SQL)
│   ├── portas.py      # ABCs: FonteDeVagas, FonteDePerfil, ProvedorLLM, Notificador, RepositorioVagas
│   └── erros.py       # SessaoExpirada, DesafioHumano, ErroDeColeta, AnaliseInvalida...
├── aplicacao/
│   ├── execucao.py    # caso de uso: coleta → filtro → análise → notificação, com lock
│   ├── analise.py     # prompt, validação Pydantic e retry — agnóstico de provedor
│   └── filtros.py     # keywords / exclude / fontes da busca
├── adaptadores/       # importar o pacote registra todos nas fábricas
│   ├── fontes/vanhack/   # Playwright: auth, listing, detail, profile, selectors, sessao, fonte
│   ├── llm/anthropic.py
│   ├── notificacao/      # formatacao, email, whatsapp
│   └── persistencia/sqlite.py   # tabelas SQLModel + RepositorioSQLite
├── fabricas.py        # Registro[T] + fontes / llms / notificadores
├── composicao.py      # raiz de composição: único lugar que liga portas a adapters
├── configuracao.py    # Settings (pydantic-settings, lê .env)
└── cli.py             # peao login | check | run | buscas | adaptadores
```

**Regra de dependência:** `dominio` não importa nada do projeto; `aplicacao` só conhece
`dominio`; adapters implementam portas; só `composicao.py`, `cli.py` e (depois) `ui/` conhecem
adapters concretos.

**Portas são `abc.ABC`:** uma classe que esquece um método abstrato nem instancia (há teste).

**Fábricas por registro:** cada adapter se registra com `@fontes.registrar("nome")` (ou `llms`,
`notificadores`). `fabricas.fontes.criar("nome", **config)`; nome errado levanta
`NomeDesconhecido` listando os disponíveis. Novo adapter = novo módulo + import em
`adaptadores/__init__.py`, nada mais.

**Identidade da vaga:** `fonte:id_externo` (`vanhack:12030`) — ids de sites diferentes colidem.
A vaga é guardada inteira em JSON (`VagaTabela.dados`); campos próprios de cada fonte vão em
`Vaga.extras`.

**Execução:** fontes rodam uma por vez (um navegador aberto de cada vez). Uma fonte que falha
não derruba as outras — vira "Falhas parciais" na execução; só falha tudo se todas falharem.
Uma análise inválida ou um notificador fora do ar também não perdem o resto. O perfil vem da
primeira fonte que implementa `FonteDePerfil`; se a leitura falhar, usa o último snapshot salvo.

---

## Análise com LLMs

- O provedor só traduz a chamada (`gerar_json(sistema, mensagens, schema)` → texto JSON ou
  recusa). **Validação e retry ficam em `aplicacao/analise.py`**, iguais para todos.
- **Nenhum provedor garante `minItems`/`maxItems` no servidor.** Na Anthropic, o
  `transform_schema` (o mesmo que o `messages.parse` usa) **move** esses limites e o
  `minimum`/`maximum` para a `description` do schema. "Exatamente 20 perguntas" é garantido pela
  validação Pydantic no cliente + até 3 tentativas devolvendo o erro ao modelo.
- **Anthropic:** `beta.messages.create` com `output_config.format` (schema transformado). Tool use
  forçado (`tool_choice` `any`/`tool`) devolve **400** nos modelos atuais — não usar. Nos modelos
  que suportam (Sonnet 5.5, Opus 5.5/5, Fable 5.1), vai o fallback de recusa do servidor
  (`fallbacks: "default"` + beta `server-side-fallback-2026-07-01`). Checar `stop_reason ==
  "refusal"` antes de ler: recusa chega como HTTP 200.
- **Antes de escrever um adapter novo:** conferir a API no SDK instalado (introspecção) e na doc
  oficial. Nunca supor nome de método ou parâmetro.
- Prompt em PT-BR; `melhorias_perfil` cita itens concretos do perfil, não conselho genérico.
  Entrada: texto do perfil + `profile_notes.md` (opcional) + a vaga em JSON.

---

## Adapter VanHack: o que o site real mostrou

**Login:** `app.vanhack.com/login` dá 404. O login fica em `auth.vanhack.com`, é **passwordless**
(magic link, Google ou LinkedIn) e tem Cloudflare Turnstile e honeypot (input "Website" — nunca
tocar). `uv run peao login` abre o Chrome visível; se for por email, **colar o link na janela
aberta**, não clicar pelo cliente de email. Sessão salva em `data/state.json`.

**Sessão:** `/jobs` é **público** — carregá-lo não prova nada. A prova é `/profile`, que dispara o
fluxo OIDC sem autenticação. O cookie `.AspNetCore.Antiforgery.*` existe mesmo deslogado.

**Navegador:** usa o Chrome instalado (`BROWSER_CHANNEL=chrome`), não o Chromium empacotado — o
Cloudflare recusa navegadores atípicos. O app logado **não** é bloqueado sob Playwright headless.

**Listagem:** busca por URL (`/jobs/{slug}-jobs`), que filtra de verdade. **Scroll infinito**
(10 cards no primeiro render, 25 depois de rolar). Busca sem resultado mostra "You're seeing 0
jobs" e devolve `[]`. A renderização às vezes demora: espera-se o card **anexado ao DOM** (não
"visível") e recarrega-se uma vez antes de desistir. Escopar links a `div.vh-cards`: a página da
vaga tem minicards de **outras** vagas.

**Vaga:** a VanHack **nunca publica a empresa** ("our hiring partner") — `empresa` é `None`.
Skills vêm em chips `span.vh-jd-skill` com os anos num `<small>`.

**Perfil (`/profile`):** formulário editável; valores em `input_value()`, dropdowns `.vh-dd`,
radios e checkboxes marcados — `inner_text()` não basta. Ids do Blazor (`0HNP0Q2EPN2A7`,
`vhdd-<guid>-button`) **mudam a cada render**: nunca usar como seletor. Estrutura:

```
section.pf-section > h5.pf-section-title + div.pf-card
  div.pf-field > label.pf-label + (div.vh-dd | input.form-control | radios | checks | pf-target-row)
  div.pf-skill-group > .pf-skill-group-title + div.pf-skill-row
  div.pf-lang-row > .pf-lang-select + .pf-lang-level
  div.pf-exp > a.pf-item-title + .pf-item-sub + div.pf-role(.pf-role-head/.pf-role-desc/.pf-chips)
```

O snapshot guarda **todos** os pares pergunta/resposta (sobrevive a mudança de texto da
pergunta). Não há campo de bio: o "headline" é a resposta de "Which role best applies...". O card
do Intro Video traz URL assinada do vídeo e a transcrição falada — só o "Level: X" é usado.

Seletores **somente** em `selectors.py`, documentados. Fixtures reais anonimizadas em
`tests/fixtures/vanhack/` (o README de lá explica a anonimização e o que auditar).

---

## Roteiro

Uma fase por vez; ao fim de cada uma: `uv run pytest`, `uv run ruff check .`, commit e push.

- [x] **Fase 1 — Núcleo hexagonal.** Domínio, portas, fábricas, composição; VanHack e Anthropic
      como adapters; FastAPI/APScheduler removidos; bug da listagem corrigido (busca vazia e
      renderização lenta); evidência salva em qualquer falha de leitura.
- [ ] **Fase 2 — LLMs:** Ollama, OpenAI, Gemini; provedor de triagem separado do de análise.
- [ ] **Fase 3 — UI CustomTkinter:** abas Vagas/Buscas/Fontes/LLMs/Perfil/Execuções/Config;
      loop asyncio em thread própria, UI recebe progresso por fila + `after()`; `keyring`.
- [ ] **Fase 4 — Agendador do Windows:** `Register-ScheduledTask -StartWhenAvailable`;
      lock entre processos com `filelock`; SQLite em modo WAL.
- [ ] **Fase 5 — APIs públicas:** Remotive, RemoteOK, Arbeitnow, Himalayas, We Work Remotely.
- [ ] **Fase 6 — Sites brasileiros:** investigar endpoint e termos antes de implementar.
- [ ] **Fase 7 — LinkedIn/Indeed:** opt-in, desligados por padrão, mesmas regras da VanHack. Os
      termos proíbem automação (risco de restrição da conta); se bloquearem, **não** escalar para
      evasão — a alternativa é ler os alertas de vaga por email (IMAP).
- [ ] **Fase 8 (opcional) — `.exe`** com PyInstaller (sem empacotar Chromium: usa o Chrome).

Pendências que dependem do Gabriel (custam dinheiro ou exigem ação dele): análise real
(`peao run --dry-run`, gasta crédito), email de teste real (SMTP no `.env`), e editar o perfil na
VanHack para validar a reanálise.

---

## Comandos

```bash
uv sync
uv run peao login                    # login manual na VanHack
uv run peao check                    # a sessão salva ainda vale?
uv run peao buscas                   # lista; `buscas adicionar NOME kw1 kw2 --exclude x`
uv run peao adaptadores              # fontes, LLMs e notificadores registrados
uv run peao run --sem-analise        # só coleta e salva; não chama LLM (não gasta crédito)
uv run peao run --dry-run            # analisa, mas não notifica
uv run peao run --fonte vanhack --llm anthropic
uv run pytest
uv run ruff check . && uv run ruff format .
```
