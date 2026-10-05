# VanHack Watcher

## Handoff (contexto vindo do claude.ai, 2026-10-05)

- **Usuário:** Gabriel, engenheiro sênior backend (PHP/Laravel, Python, TypeScript, AWS). Usa **Windows**
  (PowerShell). Converse e escreva mensagens/commits em **português do Brasil**.
- **Origem:** projeto planejado e implementado numa conversa no claude.ai. O código deste repositório é
  a versão entregue lá; nada foi executado ainda na máquina dele.
- **Decisões tomadas e motivos:**
  - Coleta **somente por navegador** (Playwright lendo o DOM). O usuário vetou usar a API interna da VanHack.
  - FastAPI + uv; SQLite; agendador dentro do app (APScheduler) com catch-up ao iniciar.
  - Perfil do candidato vem **sempre** da página /profile (sincronizado a cada execução);
    `profile_notes.md` é só complemento manual.
  - Email é o canal principal (análise completa); WhatsApp via Twilio é opcional (resumo).
  - Modelo da análise configurável em `ANALYSIS_MODEL` (padrão `claude-sonnet-5-5`).
- **Mapeamento do site:** feito em 2026-10-05 com Claude in Chrome na conta logada do usuário
  (somente leitura). Resultado em `src/vanhack_watcher/scraper/selectors.py`.
- **Ambiente:** `gh` já instalado e autenticado.

### Próxima tarefa
1. `git init -b main`, `git add .`, mostrar o `git status` e confirmar que `.env`, `data/` e `artifacts/`
   NÃO estão incluídos; commit inicial; `gh repo create vanhack-watcher --private --source=. --push`.
2. Seguir as pendências do bloco "Estado atual" abaixo, uma de cada vez, pedindo ao usuário que faça
   o login manual quando necessário (`uv run vanhack-login --headed`).


> **Estado atual (2026-10-05):** fases 1, 3–8 implementadas e com testes (19 passando, offline).
> Fase 2 parcial: seletores de listagem, detalhe e perfil mapeados no site real
> (`scraper/selectors.py`), mas as fixtures em `tests/fixtures/` são **reconstruções** da estrutura.
> Pendências, nesta ordem:
> 1. Rodar `uv run vanhack-login --headed`, depois `POST /profile/sync` e conferir `GET /profile`
>    (validar a extração dos campos do formulário e a remoção de PII).
> 2. `uv run vanhack-run --dry-run` contra o site real; corrigir seletores com base em `artifacts/`.
> 3. Substituir as fixtures pelo HTML real (`page.content()`), anonimizado.
> 4. Mapear a tela de login real (os seletores de login em `selectors.py` são genéricos).
> 5. Fase 9: tarefa no Agendador do Windows (ver README).
>
> Descobertas do mapeamento: app Blazor (LeptonX), classes `vh-*`; busca por URL
> `/jobs/{slug}-jobs` (~10 resultados, sem paginação); vaga em `/job/{id}`; cards não mostram empresa.

Serviço pessoal que, todo dia às 08:00 (America/Sao_Paulo), faz login na VanHack via navegador,
coleta as vagas por scraping, filtra por buscas configuráveis, analisa cada vaga nova com o Claude
e envia um aviso por email (completo) e WhatsApp (resumo).

Para cada vaga nova a análise contém:
- fit score (0–100) e resumo do encaixe com o perfil
- passos concretos de preparação
- exatamente 20 perguntas (técnicas e comportamentais) sobre os temas da vaga
- gaps (requisitos que faltam ou estão fracos)
- o que melhorar no perfil (CV, LinkedIn, perfil VanHack) para essa vaga

O perfil do candidato **não é mantido à mão**: a cada execução o sistema lê `https://app.vanhack.com/profile`
(mesma sessão logada), guarda um snapshot e usa sempre a versão mais recente nas análises.
Um arquivo opcional `profile_notes.md` complementa com o que não existe na VanHack (metas, o que evitar).

O FastAPI é o painel de controle (buscas, histórico, análises, status). A coleta é 100% por navegador.

---

## Regras inegociáveis

- **Nada de chamar a API interna da VanHack** (nem com httpx, nem interceptando XHR para consumir JSON).
  A coleta é feita lendo o DOM renderizado com Playwright, como um usuário.
- **Não contornar 2FA, captcha ou detecção de bot.** Se aparecerem: parar, salvar evidência,
  notificar o usuário e exigir login manual (`uv run vanhack-login --headed`).
- **Login só quando a sessão expira.** Sempre tentar primeiro com `data/state.json`.
- **Comportamento educado:** uma execução por vez, sem paralelismo de páginas, pausa aleatória de
  2–5 s entre navegações, limite de vagas detalhadas por execução (`MAX_DETAILS_PER_RUN`).
- **Segredos só no `.env`** (no `.gitignore`, junto com `data/` e `artifacts/`). Nunca logar senha
  ou cookies. Não exportar `ANTHROPIC_API_KEY` como variável global do sistema.
- Todo texto voltado ao usuário (prompts, emails, WhatsApp, mensagens de erro) em **português do Brasil**.

---

## Stack

- Python 3.12+, gerenciado com **uv** (`uv init --package`, `uv add`, `uv run`)
- `fastapi`, `uvicorn[standard]`
- `sqlmodel` (SQLite em `data/watcher.db`)
- `pydantic-settings`
- `apscheduler` 3.x (`AsyncIOScheduler`, dentro do lifespan do FastAPI)
- `playwright` (async, Chromium)
- `anthropic` (`AsyncAnthropic`)
- `aiosmtplib` (email), `httpx` (Twilio WhatsApp)
- Dev: `pytest`, `pytest-asyncio`, `ruff`

---

## Estrutura

```
vanhack-watcher/
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── profile_notes.md               # complemento manual opcional (metas, o que evitar)
├── data/                          # state.json, watcher.db (gitignored)
├── artifacts/                     # screenshots + HTML de falhas (gitignored)
├── src/vanhack_watcher/
│   ├── main.py                    # app FastAPI + lifespan (scheduler start/stop)
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── db.py                      # engine + get_session
│   ├── models.py                  # tabelas SQLModel
│   ├── schemas.py                 # Pydantic: JobAnalysis, DTOs da API
│   ├── cli.py                     # entrypoints: vanhack-login, vanhack-run
│   ├── scraper/
│   │   ├── browser.py             # cria browser/context, carrega/salva storage_state
│   │   ├── auth.py                # is_logged_in, login, detect_challenge (2FA/captcha)
│   │   ├── selectors.py           # TODOS os seletores aqui, documentados
│   │   ├── listing.py             # busca por keyword, scroll/paginação, extrai cards
│   │   ├── detail.py              # extrai dados completos da página da vaga
│   │   ├── profile.py             # extrai o perfil do usuário em /profile
│   │   └── debug.py               # dump de screenshot + HTML em artifacts/
│   ├── filters.py                 # keywords / exclude
│   ├── analyzer.py                # Claude via tool use + validação Pydantic
│   ├── notifier.py                # email por vaga, digest no WhatsApp, dry_run
│   ├── pipeline.py                # orquestra uma execução, com lock
│   ├── scheduler.py               # cron diário + misfire handling
│   └── api/
│       ├── searches.py
│       ├── jobs.py
│       ├── runs.py
│       ├── profile.py
│       └── health.py
└── tests/
    ├── fixtures/                  # HTML real salvo da listagem e de vagas
    ├── test_listing.py
    ├── test_detail.py
    ├── test_profile.py
    ├── test_filters.py
    ├── test_analyzer.py           # com cliente Anthropic mockado
    └── test_api.py
```

`pyproject.toml` deve expor os scripts:
```toml
[project.scripts]
vanhack-login = "vanhack_watcher.cli:login"   # --headed para login manual
vanhack-run   = "vanhack_watcher.cli:run"     # --dry-run para não notificar
```

---

## Configuração (`.env.example`)

```
# VanHack
VANHACK_EMAIL=
VANHACK_PASSWORD=
VANHACK_LOGIN_URL=https://app.vanhack.com/login
VANHACK_JOBS_URL=https://app.vanhack.com/jobs
VANHACK_PROFILE_URL=https://app.vanhack.com/profile
HEADLESS=true
MAX_LISTING_SCROLLS=15
MAX_DETAILS_PER_RUN=15

# Agendamento
SCHEDULE_CRON=0 8 * * *
TIMEZONE=America/Sao_Paulo

# Análise
ANTHROPIC_API_KEY=
ANALYSIS_MODEL=claude-sonnet-5-5
PROFILE_NOTES_PATH=profile_notes.md
REANALYZE_ON_PROFILE_CHANGE=true
MAX_REANALYSES_ON_CHANGE=10
MAX_ANALYSES_PER_RUN=10

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=
SMTP_PASS=
EMAIL_TO=

# WhatsApp (Twilio)
WHATSAPP_ENABLED=true
TWILIO_SID=
TWILIO_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_TO=whatsapp:+55XXXXXXXXXXX

DRY_RUN=false
```

---

## Modelo de dados

- **Search**: id, name, keywords (list[str]), exclude (list[str]), active, created_at
- **Job**: id (id/slug da VanHack, extraído da URL), title, company, url, location, salary (nullable),
  skills (list[str]), description (texto completo), matched_searches (list[str]),
  status (`nova` | `estudando` | `aplicada` | `descartada`), first_seen_at, scraped_at
- **Analysis**: id, job_id, fit_score, resumo, preparacao, perguntas, gaps, melhorias_perfil,
  model, profile_snapshot_id, created_at (uma vaga pode ter várias análises; a mais recente é a vigente)
- **ProfileSnapshot**: id, data (JSON estruturado: headline, resumo, skills, experiências, formação,
  idiomas, preferências de vaga/salário/local, links), text (versão em texto para o prompt),
  content_hash (sha256 do JSON normalizado), scraped_at. Só grava novo snapshot se o hash mudar.
- **Run**: id, started_at, finished_at, trigger (`cron` | `manual`), status (`ok` | `erro` | `login_required`),
  jobs_listed, jobs_new, jobs_analyzed, profile_changed (bool), error, artifact_path

Listas guardadas como JSON. Criar tabelas no startup (`SQLModel.metadata.create_all`).

---

## Fluxo do pipeline

1. Adquirir lock (`asyncio.Lock`). Se já houver execução rodando → retornar 409 / pular.
2. Abrir browser com `data/state.json` se existir.
3. Abrir `VANHACK_JOBS_URL`. Se redirecionar para login ou mostrar formulário de login → `auth.login()`.
4. `auth.login()`: preencher email/senha, enviar, aguardar navegação. Rodar `detect_challenge()`:
   se houver 2FA/captcha/erro de credencial → dump em artifacts, `Run.status=login_required`,
   notificar e encerrar. Sucesso → salvar `state.json`.
5. **Sync de perfil**: abrir `VANHACK_PROFILE_URL`, extrair os dados (expandir seções colapsadas /
   "ver mais" se existirem), normalizar e calcular hash. Se mudou: gravar novo ProfileSnapshot,
   marcar `Run.profile_changed` e, se `REANALYZE_ON_PROFILE_CHANGE`, enfileirar reanálise das vagas
   com status `nova` ou `estudando` (até `MAX_REANALYSES_ON_CHANGE`). Se a extração falhar,
   seguir com o último snapshot válido e registrar o aviso no Run (nunca analisar sem perfil:
   se não houver nenhum snapshot, abortar com erro).
6. Para cada Search ativa: aplicar a keyword pelo campo de busca da página, rolar/paginar até não
   surgirem cards novos ou atingir `MAX_LISTING_SCROLLS`, extrair (id, title, company, url) dos cards.
7. Unir resultados por id, registrar quais buscas casaram, descartar ids já existentes no banco.
8. Para cada vaga nova (até `MAX_DETAILS_PER_RUN`): abrir a página, extrair dados completos, pausa 2–5 s.
9. Aplicar `filters.py` sobre título + descrição completa (keywords da busca, exclude). Persistir Job.
10. Analisar até `MAX_ANALYSES_PER_RUN` vagas, ordem de chegada.
11. Notificar: 1 email por vaga analisada + 1 mensagem de WhatsApp com o digest
    (título, empresa, fit, link; ordenado por fit). Se o perfil mudou, o digest começa com
    "Perfil atualizado" e as reanálises entram no email com o fit anterior → novo.
    Se `DRY_RUN`, apenas logar.
12. Fechar `Run` com contadores. Qualquer exceção → dump em artifacts, `Run.status=erro`,
    notificação curta de erro.

---

## Scraping: diretrizes

- Seletores **somente** em `selectors.py`, cada um com comentário do que representa.
  Preferência: `get_by_role` / `get_by_label` / `get_by_placeholder` / atributos `data-*` / `href`.
  Evitar classes CSS geradas (ex.: `css-1x2y3z`).
- Id da vaga: derivar da URL do card (ex.: `/jobs/<id>`), não de texto.
- Esperas por estado (`locator.wait_for`, `expect`), nunca `sleep` fixo para sincronizar
  (o `sleep` aleatório é só para o ritmo educado).
- User agent padrão do Chromium; nada de técnicas de evasão.
- `debug.dump(page, label)` salva `artifacts/<timestamp>_<label>.png` e `.html`.

### Página de perfil (`/profile`): particularidades já observadas

- É um **formulário editável**, não uma página de leitura: grande parte dos dados (cargo, top 3 skills,
  skills secundárias, países de preferência, idiomas, links) está em `value` de inputs/selects/autocompletes.
  `inner_text()` NÃO captura esses valores; extrair lendo `input_value()`, opções selecionadas,
  checkboxes/radios marcados e chips.
- Seções: General, Professional Overview, Relocation, Social Profile, Languages, Experience,
  Education, Side Projects, além do Intro Video (nível de inglês, notas por critério, transcrição).
- Experiências vêm em texto (empresa, cargo, período, descrição, tags de skills): extrair cada uma.
- **Nunca** ler o perfil clicando em salvar, editar, gravar vídeo ou qualquer controle que altere dados.
- **PII fora do snapshot e do prompt:** não armazenar email, telefone, documentos, status de visto,
  validade de passaporte nem a URL assinada do currículo (contém token temporário).
  Guardar apenas o que serve para casar com vagas.

---

## Análise com Claude

- Prompt de sistema em PT-BR: mentor técnico de carreira para vagas internacionais remotas.
- Entrada: `text` do ProfileSnapshot mais recente + `profile_notes.md` (se existir) + dados completos da vaga.
- `melhorias_perfil` deve citar itens concretos do perfil VanHack atual (ex.: "skill X não aparece
  na lista de skills", "headline não menciona Y"), não conselhos genéricos.
- Forçar **tool use** com uma ferramenta `registrar_analise` cujo input schema vem de
  `JobAnalysis.model_json_schema()` e `tool_choice` obrigatório nessa ferramenta.
- `JobAnalysis` (Pydantic): `fit_score: int (0–100)`, `resumo: str`, `preparacao: list[str]` (≥3),
  `perguntas: list[str]` (exatamente 20), `gaps: list[str]`, `melhorias_perfil: list[str]` (≥3).
- Validação falhou → até 2 novas tentativas informando o erro ao modelo. Persistir falha no Run.

---

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | último Run, se state.json existe, próxima execução agendada |
| GET | `/searches` | listar |
| POST | `/searches` | criar |
| PUT | `/searches/{id}` | atualizar |
| DELETE | `/searches/{id}` | remover |
| GET | `/jobs` | filtros: `status`, `min_score`, `search`, paginação |
| GET | `/jobs/{id}` | vaga + análise vigente |
| PATCH | `/jobs/{id}` | alterar `status` |
| POST | `/jobs/{id}/reanalyze` | nova análise (ex.: após editar profile_notes.md) |
| GET | `/profile` | snapshot mais recente (data + text) |
| GET | `/profile/history` | snapshots com data e campos alterados em relação ao anterior |
| POST | `/profile/sync` | sincroniza só o perfil, sem buscar vagas |
| POST | `/runs` | dispara execução em background (409 se já rodando) |
| GET | `/runs` | histórico |

Rodar com **1 worker** (o scheduler vive no processo).

---

## Agendamento

- `AsyncIOScheduler` com `CronTrigger.from_crontab(SCHEDULE_CRON, timezone=TIMEZONE)`.
- `misfire_grace_time` alto (ex.: 6 h) + `coalesce=True`: se o computador estava desligado às 08:00,
  executa uma vez ao subir o app.
- `max_instances=1`.

---

## Fases e critérios de pronto

Implementar **uma fase por vez**, rodar testes e `uv run ruff check` ao final de cada uma,
e pedir validação ao usuário antes de seguir quando a fase depender do site real.

### Fase 1: Setup
- [ ] `uv init --package`, dependências instaladas, `uv run playwright install chromium`
- [ ] `.env.example`, `.gitignore` (`.env`, `data/`, `artifacts/`), `profile_notes.md` de exemplo
- [ ] `config.py` carregando o `.env`; `uv run pytest` passa (teste trivial)

### Fase 2: Descoberta (com o usuário)
- [ ] Usuário roda `uv run playwright codegen https://app.vanhack.com/login` e compartilha as interações
- [ ] Mapear seletores: formulário de login, campo de busca, card de vaga, link, paginação/scroll,
      campos da página de detalhe, indicadores de 2FA/captcha/erro de login
- [ ] Mapear a página `/profile`: todas as seções e como expandir conteúdo colapsado
- [ ] Salvar em `tests/fixtures/`: `listing.html`, `profile.html` e ao menos 2 `detail_*.html` reais
      (remover dados pessoais do HTML)
- [ ] `selectors.py` preenchido e comentado

### Fase 3: Browser + autenticação
- [ ] `vanhack-login --headed` abre o navegador para login manual e salva `state.json`
- [ ] `is_logged_in()` e `login()` automático funcionam contra o site real
- [ ] `detect_challenge()` identifica 2FA/captcha/credencial inválida e gera dump

### Fase 4: Listagem + detalhe
- [ ] `listing.py` e `detail.py` extraem corretamente a partir das fixtures (testes offline)
- [ ] Execução real com uma keyword lista vagas e detalha 2 delas

### Fase 4b: Sync de perfil
- [ ] `scraper/profile.py` extrai o perfil a partir da fixture (teste offline)
- [ ] Hash estável: rodar duas vezes sem mudança no site não cria novo snapshot
- [ ] Execução real grava o primeiro snapshot

### Fase 5: Banco + buscas
- [ ] Models criados, CRUD de `/searches` com testes

### Fase 6: Analyzer
- [ ] Tool use + validação; teste com cliente mockado (sucesso e retry)
- [ ] Análise real de uma vaga das fixtures com 20 perguntas válidas

### Fase 7: Notifier
- [ ] Email por vaga (texto legível, seções claras) e digest WhatsApp ≤ 1500 caracteres
- [ ] `DRY_RUN` só loga; teste com SMTP/Twilio mockados

### Fase 8: Pipeline + scheduler + API
- [ ] `vanhack-run --dry-run` executa o fluxo completo contra o site real
- [ ] Lock impede execução concorrente; `Run` registrado em todos os desfechos
- [ ] Alterar algo no perfil VanHack → próxima execução detecta, grava snapshot e reanalisa
- [ ] `/jobs`, `/runs`, `/profile`, `/health` funcionando; scheduler visível no `/health`

### Fase 9: Deploy
- [ ] Documentar no README como rodar como serviço:
      Windows (NSSM ou Agendador de Tarefas), Linux (systemd), e opção Docker para VPS
- [ ] Documentar o procedimento de sessão expirada em VPS
      (logar localmente e copiar `data/state.json`)

---

## Comandos úteis

```bash
uv sync
uv run vanhack-login --headed
uv run vanhack-run --dry-run
uv run uvicorn vanhack_watcher.main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format .
```
