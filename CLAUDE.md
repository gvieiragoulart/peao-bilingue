# Peão Bilíngue

Radar pessoal de vagas para o Gabriel: coleta vagas em vários sites, filtra por buscas
configuráveis e avisa das vagas novas por email e WhatsApp. A análise de encaixe por LLM é
**pedida vaga a vaga** no app, com o LLM e o perfil escolhidos na hora. App desktop Windows
(CustomTkinter), com a coleta diária disparada pelo Agendador do Windows.

Cada análise traz: fit score (0–100), resumo do encaixe, passos de preparação, **exatamente 20**
perguntas de entrevista, gaps e o que melhorar no perfil (CV, LinkedIn, VanHack).

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

## Estado atual (2026-10-08)

**Fases 1 a 5 e 8 do novo roteiro concluídas** (a 6 aguarda decisão; a 7 não começou), mais a mudança de 07/10 pedida pelo Gabriel: a
coleta não chama LLM nenhum; cada vaga é analisada pelo botão **Analisar** da aba Vagas, com o
LLM escolhido (Anthropic, Ollama, OpenAI, Gemini) e o **perfil da fonte** da vaga (cada fonte
tem o seu). A triagem automática saiu. 264 testes offline; `ruff` e `mypy --strict` limpos.
FastAPI, uvicorn e APScheduler saíram. Banco em `data/peao.db` (o antigo `watcher.db` ficou
intocado) com 18 vagas reais, nenhuma analisada ainda. Três buscas cadastradas: Python,
PHP/Laravel, React/TypeScript — sem `exclude`, porque filtrar "junior" descartaria vaga sênior
que diz "mentor junior engineers".

O banco evolui por **migração aditiva automática** (`migrar` em `persistencia/sqlite/banco.py`): o
`create_all` não acrescenta colunas a tabelas existentes, então campo novo em model ganha
`ALTER TABLE ADD COLUMN` com o default do model. Mudança não aditiva exige migração à mão.

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
- **Segredos no Cofre de Credenciais do Windows** (via `keyring`, serviço `peao-bilingue`), nunca
  em arquivo versionado. O `.env` (no `.gitignore`, junto com `data/` e `artifacts/`) é só
  fallback da CLI. Nunca logar senha nem cookie.
- **PII fora do snapshot e do prompt:** nada de email, telefone, documento, visto, passaporte,
  cidadania, nome, nem URLs assinadas (currículo, vídeo). Há teste travando isso.
- Todo texto voltado ao usuário em **português do Brasil**.

---

## Arquitetura: portas e adaptadores

```
src/peao_bilingue/
├── dominio/
│   │                  # um módulo por subdomínio: entidades (pydantic, sem SQL) + portas (ABCs)
│   ├── vagas.py       # Vaga, VagaResumo, Skill, StatusVaga, VagaListada · RepositorioVagas
│   ├── buscas.py      # Busca · RepositorioBuscas
│   ├── perfil.py      # Perfil · FonteDePerfil, RepositorioPerfis
│   ├── analise.py     # JobAnalysis, AnaliseSalva, Mensagem, RespostaLLM · ProvedorLLM,
│   │                  #   RepositorioAnalises
│   ├── coleta.py      # Execucao, StatusExecucao, Gatilho · FonteDeVagas, SessaoManual, Trava,
│   │                  #   RepositorioExecucoes
│   ├── avisos.py      # Notificador
│   ├── agenda.py      # SituacaoAgenda · Agendador
│   ├── repositorio.py # Repositorio = as cinco portas de repositório juntas (UI e composição)
│   └── erros.py       # SessaoExpirada, DesafioHumano, ErroDeColeta, AnaliseInvalida...
├── aplicacao/
│   ├── execucao.py    # coleta: buscar → filtrar → guardar → avisar (sem LLM), com lock
│   ├── analise.py     # análise sob demanda: prompt, validação e retry — agnóstico de provedor
│   └── filtros.py     # keywords / exclude / fontes da busca
├── adaptadores/       # importar o pacote registra todos nas fábricas
│   ├── fontes/vanhack/   # Playwright: auth, listing, detail, profile, selectors, sessao, fonte
│   ├── llm/anthropic.py
│   ├── notificacao/      # formatacao, email, whatsapp
│   ├── agendamento/windows.py   # Agendador de Tarefas via PowerShell
│   └── persistencia/     # sqlite/ (tabelas, banco, um arquivo por agregado e RepositorioSQLite
│                         #   juntando os cinco), trava.py (filelock)
├── fabricas.py        # Registro[T] + fontes / llms / notificadores
├── composicao.py      # raiz de composição: único lugar que liga portas a adapters
├── configuracao.py    # Settings: config.json + cofre do Windows + .env (fallback)
├── ui/                # CustomTkinter: app, executor assíncrono, abas, componentes
└── cli.py             # peao login | check | run | buscas | agenda | adaptadores
```

**Configuração:** precedência `config.json` > cofre > variáveis de ambiente > `.env` > padrão. A
interface grava em `data/config.json` (público) e no cofre (campos em `SEGREDOS`) via
`configuracao.salvar()`, que também atualiza o `settings` **no lugar** — vários módulos fazem
`from configuracao import settings`, e trocar o objeto não chegaria a eles. `PEAO_DADOS` muda a
pasta de dados (padrão `data`); os testes a apontam para um temporário e trocam o keyring por um
em memória **antes** de importar o projeto, para nunca tocar na configuração real.

**Interface (`ui/`):** o Tkinter é síncrono e o núcleo é assíncrono (Playwright). As corrotinas
rodam num loop asyncio numa thread própria (`ExecutorAssincrono`); os resultados voltam por
`after()` (`acompanhar`) e os logs por uma fila (`FilaDeLog`). **Nenhum widget é tocado fora da
thread da interface** — callbacks que vêm do worker (ex.: `aviso` do login) só enfileiram.
Verificado no Windows: Playwright funciona nessa thread (loop Proactor) sem travar a janela.
Os formulários de LLMs e avisos são montados a partir de `campos` que cada adapter declara, com
o tipo do widget inferido do próprio `Settings`. Fontes com login manual implementam a porta
`SessaoManual` e ganham botões de login/verificação automaticamente. `peao-ui` é gui-script:
abre sem console.

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

**Vaga repetida entre fontes** (13/10): a mesma vaga aparece em vários sites (a Lemon.io publica
no Remotive, no Himalayas e no WWR). `Vaga.assinatura()` = empresa + título normalizados
(minúsculas, sem acento, só letras e números: "Full-stack" = "full stack", "Lemon.io" = "lemon
io"). Vale só entre **fontes diferentes**: na mesma fonte, título e empresa iguais são vagas
diferentes (a Bjak tem "Frontend Engineer" em Singapura e na Irlanda, no Remote OK). Sem empresa
não há assinatura — a VanHack nunca publica a empresa, e só o título juntaria vagas que não têm
nada a ver. A repetida é **guardada** com `repete=<chave da original>` (senão seria detalhada de
novo a cada coleta, gastando o limite por fonte), mas não conta como nova, não vai no aviso e
não aparece na lista; o detalhe da original mostra "Também em <fonte>: <link>". Vagas de antes
da coluna são assinadas e juntadas ao abrir o banco (`_assinar_vagas_antigas`, uma vez); no
banco real, 2 pares da Lemon.io.

**Pesquisa** na aba Vagas (`listar_vagas(pesquisa=)`, `Vaga.contem`): cada palavra precisa
aparecer no título, empresa, local, skills ou descrição, sem ligar para acento nem maiúsculas.

**Coleta (`executar`):** buscar → filtrar → guardar → avisar; **não chama LLM**. Fontes rodam
uma por vez (um navegador aberto de cada vez). Uma fonte que falha não derruba as outras — vira
"Falhas parciais" na execução; só falha tudo se todas falharem. Cada fonte que implementa
`FonteDePerfil` lê e guarda **o próprio perfil** a cada coleta; se a leitura falhar, fica o
último salvo dela. **Avisos** (resumo das vagas novas: título, fonte, link) só com
`avisar=True` — a coleta agendada e `peao run --avisar`; a do botão não avisa, porque quem
pediu está olhando. Aviso que falha também vira "Falhas parciais" (as vagas ficam salvas). Os
canais começam desligados (`NOTIFICADORES=[]`): ligado sem estar preenchido, todo aviso falharia.
**Aviso de problema** (`Notificador.avisar_problema`, 13/10): com `avisar=True`, fonte que falha
(ou a execução inteira, se não foi fonte) também é avisada — "VanHack: Sessão da VanHack
expirada…". Sem isso a sessão vencida fazia a coleta agendada falhar todo dia em silêncio. Repete
a cada coleta enquanto não for resolvido, de propósito: é o lembrete. O texto é o da exceção,
sem o nome da classe (`fonte.rotulo: mensagem`).

**Perfil por fonte:** o perfil cadastrado na VanHack não é o do LinkedIn. `Perfil.fonte`; o
repositório guarda, deduplica e mostra histórico **por fonte**. Bancos antigos ganharam a coluna
`fonte` com `vanhack` (era a única fonte com perfil) — conferido numa cópia do banco real.

---

## Coleta agendada e concorrência

- **Tarefa** registrada pelo PowerShell 5.1 (`Register-ScheduledTask`; o `schtasks` não tem
  `-StartWhenAvailable`): diária, roda ao ligar o PC se a hora passou com ele desligado,
  `-MultipleInstances IgnoreNew`, limite de 2 h. Executa `.venv\Scripts\pythonw.exe -m
  peao_bilingue.cli run --agendado` (coleta e avisa das vagas novas e dos problemas; nada de LLM) — ou o
  próprio `PeaoBilingue.exe run --agendado`, ver "Executável" — com a
  **pasta do projeto como diretório de trabalho** —
  `data/`, `.env` e `profile_notes.md` são relativos a ela. Nome da tarefa em ASCII: a saída
  do PowerShell 5.1 vem na página de código do console.
- **Script sempre com `$ErrorActionPreference = 'Stop'` e `exit 0` no fim.** Sem isso,
  `Get-ScheduledTask -ErrorAction SilentlyContinue` com a tarefa inexistente sai com código 1
  e nenhuma mensagem. O `ConvertTo-Json` do 5.1 serializa data como `\/Date(...)\/`: as datas
  são formatadas em ISO dentro do script. `LastRunTime` 30/11/1999 = nunca rodou;
  `LastTaskResult` 0 = ok, 1 = nossa falha, 267009 = rodando, 267011 = nunca rodou.
- O `pythonw` não tem console: com `--agendado`, o registro vai para `data/coleta.log`
  (rotativo, 1 MB × 3).
- **Uma execução por vez, entre processos:** `TravaDeArquivo` (`filelock` em
  `data/execucao.lock`). A mesma instância do `FileLock` é **reentrante** — cada aquisição usa
  uma instância nova, senão a segunda execução no mesmo processo entraria. Verificado no Windows:
  app/CLI e tarefa agendada se excluem.
- **Execução órfã:** com a trava na mão, nenhuma outra execução está viva — o que ainda consta
  "rodando" é de processo que morreu (app fechado no meio, PC desligado, limite de tempo) e é
  marcado como erro no início da execução seguinte.
- SQLite em **WAL** com `busy_timeout` de 5 s: a interface lê enquanto a tarefa grava.
- **PC suspenso no meio da coleta:** o processo volta junto com o PC e o Playwright falha com
  `ERR_NETWORK_IO_SUSPENDED`; a execução fica registrada como erro (visto em 06/10). Sem
  `-WakeToRun` de propósito: acordar o notebook do usuário é invasivo.

---

## Executável (Fase 8)

- `empacotamento/peao_bilingue.spec`, build com
  `uv run --group empacotar pyinstaller empacotamento/peao_bilingue.spec --noconfirm` →
  `dist/PeaoBilingue/PeaoBilingue.exe` (~170 MB, a maior parte o driver node do Playwright).
  O PyInstaller fica no grupo `empacotar`, fora do `uv sync` normal e do CI.
- **Um .exe para os dois papéis** (`inicio.py`): sem argumentos abre a janela, com argumentos é
  a CLI. É de janela (`console=False`); a tarefa agendada roda `PeaoBilingue.exe run --agendado`
  (`comando_da_coleta()` escolhe entre isso e o `pythonw` do projeto por `sys.frozen`).
- **Dados em `%LOCALAPPDATA%\PeaoBilingue`** quando congelado (`configuracao.pasta_base()`):
  `data/`, `.env`, `profile_notes.md` e `artifacts/` saem de lá, não da pasta do .exe nem do
  diretório de trabalho. No projeto continua tudo relativo à pasta atual.
- Entram à mão no spec: os submódulos de `peao_bilingue` (adapters são importados pelo registro),
  os backends do `keyring` + metadata (achados por entry points), `win32ctypes.core` e o dialeto
  `sqlite` do SQLAlchemy. O Chromium do Playwright **não** entra: usa o Chrome instalado.
- **Instalação do Gabriel (13/10):** programa em `%LOCALAPPDATA%\Programs\PeaoBilingue`, dados
  em `%LOCALAPPDATA%\PeaoBilingue` (migrados do `data/` do projeto), atalho no Menu Iniciar e a
  tarefa das 08:00 chamando o .exe. O `data/` do projeto virou só cópia de desenvolvimento.
- **O Claude desktop é MSIX:** pasta **nova** criada em `AppData` por processo aberto pelo shell
  do agente (inclusive o .exe) vai para `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\...` — só o
  agente a vê. Assim a primeira migração "sumiu": a tarefa agendada abriu um banco vazio e saiu
  com código 0 sem registro. Para instalar, atualizar ou testar o .exe de verdade, usar uma
  **tarefa agendada temporária** (roda fora do contêiner) e removê-la depois.
- **Bug achado pelo .exe (existia também no projeto):** se o `__aenter__` da VanHack falhava
  depois de abrir o navegador (sessão expirada, desafio), o `async with` não chamava o
  `__aexit__` e o Chrome + driver seguravam o processo — a coleta agendada com sessão vencida
  nunca terminava (até o limite de 2 h). Agora o `__aenter__` fecha tudo antes de relançar.

---

## Análise com LLMs

- **Sob demanda:** `analisar_vaga(repositorio, provedor, chave, perfil_de=None)`, chamada pelo
  botão Analisar da aba Vagas. Usa o perfil da **fonte da vaga**; o seletor de perfil escolhe o
  de outra fonte (o caminho para fontes sem perfil, como as APIs públicas da Fase 5). Sem perfil
  lido → `PerfilAusente`, antes de gastar com o LLM. A análise guarda o `perfil_id`: quando a
  mesma fonte ganha snapshot mais novo, `AnaliseSalva.perfil_desatualizado` e a tela sugere
  analisar de novo — não há mais reanálise automática.
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
- **Ollama:** `format` recebe o JSON Schema (vira gramática; a saída já sai no formato). O
  contexto padrão do Ollama é pequeno e **trunca o prompt em silêncio** — `num_ctx` sempre
  explícito (`OLLAMA_CONTEXTO`, 8192 cabe nos 6 GB com modelo de 8B). Desligado ou modelo não
  baixado viram `ProvedorIndisponivel` com a instrução (`ollama serve` / `ollama pull`).
- **OpenAI:** `chat.completions.create` com `response_format` estrito (o conversor
  `to_strict_json_schema` é o mesmo do `parse`). Não usar `parse`: ele valida dentro do SDK e
  engole o texto que a aplicação devolve ao modelo no retry. Recusa vem em `message.refusal`.
- **Gemini:** o assistente se chama `"model"`; bloqueio de segurança **não** levanta exceção —
  chega como resposta sem texto e `finish_reason` `SAFETY`/`PROHIBITED_CONTENT`/`BLOCKLIST`.
- **OpenAI e Gemini não têm modelo padrão** (`OPENAI_MODELO`/`GEMINI_MODELO` obrigatórios): o
  catálogo muda e um nome inventado só falharia na hora de rodar.
- **Triagem removida em 07/10:** com a análise pedida vaga a vaga, o filtro automático por LLM
  barato perdeu a razão de existir.
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

## Fontes por API

Sem login e sem perfil: a análise de uma vaga delas usa o perfil escolhido no seletor (o padrão
cai no primeiro perfil salvo, hoje o da VanHack). Descrição em HTML vira texto com uma linha por
parágrafo (`adaptadores/fontes/html.py`). Fixture = resposta real salva em
`tests/fixtures/<fonte>/`; os testes usam `ApiFalsa` (em `dubles.py`, sobre
`httpx.MockTransport`), sem rede, e contam as chamadas.

**Base `FonteDeApi`** (`adaptadores/fontes/api.py`), dois jeitos de consultar:
- **lista inteira** (`parametros()`): uma chamada por coleta, e cada termo é filtrado localmente
  com o mesmo texto do filtro das buscas — Remotive, Remote OK, Arbeitnow;
- **por termo** (`parametros_do_termo()`): a API já busca, uma chamada por termo, com `pausa_s`
  entre chamadas de verdade — Himalayas;
- **algumas consultas fixas** (`consultas()`): a lista vem em partes — We Work Remotely, um feed
  por categoria. `decodificar()` troca o JSON por outro formato (RSS).
Cache por consulta em `data/cache/<fonte>[-<hash>].json` (`validade_s`, padrão 6 h; só vale para
a mesma consulta); `detalhar` não chama a API. Cada fonte define `url`, os parâmetros e
`converter()`. 429 vira `ErroDeColeta` legível.

**Remotive** (`GET https://remotive.com/api/remote-jobs?category=software-dev`). Termos, no
aviso legal da própria resposta: linkar a vaga no Remotive **e** citar o Remotive como fonte;
**no máximo ~4 chamadas por dia** (mais de 2 por minuto são bloqueadas); dados com 24 h de
atraso; não republicar em outros sites de vagas. Por isso **uma chamada por coleta** (a
categoria vem inteira — 17 vagas em 07/10 — e cada termo é filtrado localmente com o mesmo
texto do filtro das buscas) e **cache de 6 h** em `data/cache/remotive.json`. O `limit` da API
foi ignorado no teste real. Salário vem `""` quando não informado. A listagem já traz a vaga
inteira: `detalhar` não chama a API. Desligada por padrão: liga na aba Fontes.

**Remote OK** (`GET https://remoteok.com/api`). Termos no primeiro item da resposta: linkar a
vaga no Remote OK (sem `nofollow`) e citar "Remote OK"; não usar o logo. Sem limite declarado;
a base já faz uma chamada por coleta. Vêm as ~100 vagas mais recentes de **todas as áreas**,
com a descrição **resumida** (o texto inteiro só no site, que não é raspado). Três armadilhas:
- toda descrição termina com uma frase anti-spam ("Please mention the word **X** and tag R…")
  cujo token é o **IP de quem chamou** em base64 — `limpar_descricao` tira a frase e qualquer
  token solto; na fixture o token é o de `2001:db8::1` (documentação);
- texto em UTF-8 lido como Latin-1 ("â€“"), vindo do próprio servidor — `consertar_codificacao`;
- `<img>` com imagem em base64 escapado no meio do texto, às vezes cortado — removido.
Salário em `salary_min`/`salary_max` (0 = não informado); `location` vem `""` quando a vaga não
diz. 12 vagas na primeira coleta real (07/10).

**Arbeitnow** (`GET https://www.arbeitnow.com/api/job-board-api?visa_sponsorship=true`). Termos
(`meta.terms` da resposta e seção 11 dos termos do site): API gratuita, "não abuse", **linkar de
volta** para o Arbeitnow; o acesso pode ser revogado. Limite de 50 chamadas
(`X-RateLimit-Limit`). Só vagas **com patrocínio de visto** — o caminho de relocação, como na
VanHack; a lista padrão é de vagas locais na Alemanha, muitas em alemão. Em 07/10: 312 vagas numa
página só. `remote=true` é **ignorado** pela API. A descrição vem com o HTML **escapado**, às
vezes só em parte (`&lt;p&gt;` dentro de tags de verdade): `descricao_em_texto` converte e, se
sobrar tag de fechamento, converte de novo. `created_at` é epoch. Primeira coleta real (08/10):
93 vagas casaram com as buscas, 15 novas (o limite por fonte).

**Himalayas** (`GET https://himalayas.app/jobs/api/search?q=<termo>&country=BR&sort=recent`).
Termos (https://himalayas.app/api): linkar a vaga no Himalayas **e** citar o Himalayas; não
republicar em outros sites; abuso dá 429. **No máximo 20 vagas por chamada** e mais de 5.000 na
lista inteira, então a busca é **por termo** (`parametros_do_termo` na base): uma chamada por
palavra-chave das buscas (8 hoje), **2 s de pausa** entre chamadas de verdade e cache de **12 h por
termo** (os dados mudam a cada 24 h). `country=BR` (`HIMALAYAS_PAIS`) traz só vagas abertas ao
Brasil ou ao mundo — sem ele, 3 de 18 serviam. O id é `empresa/slug`: o slug sozinho se repete
entre empresas. `locationRestrictions` vira o "local" (até 3 países; acima disso, a contagem) e
fica inteiro em `extras["paises"]`. Primeira coleta real (08/10): 117 listadas, 15 novas.

**We Work Remotely** (RSS: `https://weworkremotely.com/categories/<categoria>.rss`). A página do
feed diz: *"Anyone can use the feed, all we ask is that you attribute the links back to We Work
Remotely."* O feed geral (`remote-jobs.rss`) traz só as ~90 mais recentes de **todas** as áreas —
faltavam nele 38 das 57 vagas de programação —, então são os feeds de back-end, full-stack e
front-end: **3 chamadas por coleta**, 2 s de pausa, cache de 6 h. O título vem "Empresa: Cargo";
`skills` vem "A, B, and C". O WebFetch leva 403 do Cloudflare deles, mas o acesso honesto (nosso
User-Agent) recebe 200 — nada de disfarce. XML pelo `ElementTree` da stdlib (o expat do Python já
se protege de expansão de entidades). Primeira coleta real (08/10): 27 listadas, 15 novas.

---

## Sites brasileiros (Fase 6): o que os termos permitem

Investigado em 08/10, antes de qualquer código, como o roteiro manda (termos lidos no site de
cada um, com acesso honesto):

| Site | API/feed oficial | O que os termos dizem | Veredito |
|---|---|---|---|
| Gupy | só para empresas clientes | proíbe "agregar, copiar ou duplicar partes do Gupy [...] incluindo oportunidades de trabalho" | **não** |
| Remotar | não | proíbe "mecanismos, software ou scripts"; cópia por "Robot/Crawler" "expressamente proibido" | **não** |
| GeekHunter | não | proíbe "scraping, spiders, crawlers, bots" sem autorização prévia e escrita | **não** |
| Trampos | não | mesma cláusula da Remotar (scripts e robôs proibidos) | **não** |
| Programathor | não (`/jobs.rss` dá 500) | **silencia** sobre acesso automatizado; `robots.txt` libera as páginas de vagas | **a decidir pelo Gabriel** |

O Programathor exigiria ler o HTML das páginas (não há alternativa oficial): os termos não
proíbem, mas também não autorizam. Fica parado até o Gabriel decidir.

---

## Roteiro

Uma fase por vez; ao fim de cada uma: `uv run pytest`, `uv run ruff check .`, `uv run mypy`, commit e push.

- [x] **Fase 1 — Núcleo hexagonal.** Domínio, portas, fábricas, composição; VanHack e Anthropic
      como adapters; FastAPI/APScheduler removidos; bug da listagem corrigido (busca vazia e
      renderização lenta); evidência salva em qualquer falha de leitura.
- [x] **Fase 2 — LLMs:** Ollama, OpenAI, Gemini; contrato comum testado contra os quatro.
      **Falta validar contra os serviços reais:** o Ollama não está instalado na máquina, e
      OpenAI/Gemini precisam de chave.
- [x] **Fase 3 — UI CustomTkinter:** abas Vagas/Buscas/Fontes/LLMs/Perfil/Execuções/
      Configurações; executor assíncrono em thread própria; segredos no cofre; janela conferida
      por captura de tela (corrigidos botões cortados e coluna fora da borda). A descrição da vaga
      passou a manter os parágrafos — melhora a tela e o prompt.
- [x] **Fase 4 — Agendador do Windows:** tarefa diária pelo app ou por `peao agenda`; lock
      entre processos com `filelock`; SQLite em WAL; execuções órfãs encerradas. Verificado de
      ponta a ponta: a tarefa roda o `pythonw` na pasta certa, grava em `coleta.log`, e app e
      tarefa se excluem. Corrigido de quebra o teste de interface intermitente (ver "Testes").
- [x] **Análise sob demanda e perfil por fonte** (pedido de 07/10): a coleta não chama LLM;
      botão Analisar com seletor de LLM e de perfil; um perfil por fonte; triagem e reanálise
      automática removidas; avisos viraram resumo das vagas novas após a coleta agendada.
- [x] **Fase 5 — APIs públicas:** Remotive, Remote OK, Arbeitnow (Alemanha com visto),
      Himalayas (aberto ao Brasil) e We Work Remotely (RSS), sobre a base `FonteDeApi`. Termos
      conferidos um a um e documentados em "Fontes por API"; todas desligadas por padrão.
- [~] **Fase 6 — Sites brasileiros:** investigação feita (ver "Sites brasileiros"): Gupy,
      Remotar, GeekHunter e Trampos proíbem; o Programathor silencia e só daria por HTML —
      **aguarda decisão do Gabriel**.
- [ ] **Fase 7 — LinkedIn/Indeed:** opt-in, desligados por padrão, mesmas regras da VanHack. Os
      termos proíbem automação (risco de restrição da conta); se bloquearem, **não** escalar para
      evasão — a alternativa é ler os alertas de vaga por email (IMAP).
- [x] **Fase 8 — `.exe`** com PyInstaller, uma pasta, sem Chromium (ver "Executável").
      Verificado sem Python/uv no PATH: janela abre, CLI coleta, o Agendador chama o .exe.

Pendências que dependem do Gabriel (custam dinheiro ou exigem ação dele): primeira análise real
pelo botão Analisar (com o Claude gasta crédito; com o Ollama é grátis, mas precisa instalar),
aviso real por email (preencher o SMTP, ligar o canal em Configurações e rodar
`peao run --avisar`), e editar o perfil na VanHack para ver o aviso de perfil desatualizado.

---

## Comandos

```bash
uv sync
uv run peao-ui                       # o app desktop
uv run peao login                    # login manual na VanHack (--fonte para outras)
uv run peao check                    # a sessão salva ainda vale?
uv run peao buscas                   # lista; `buscas adicionar NOME kw1 kw2 --exclude x`
uv run peao adaptadores              # fontes, LLMs e notificadores registrados
uv run peao run                      # coleta e salva; não chama LLM (análise é no app)
uv run peao run --fonte vanhack      # só uma fonte
uv run peao run --avisar             # também avisa das vagas novas e dos problemas
uv run peao agenda                   # situação da coleta diária
uv run peao agenda ativar --horario 08:00            # ou `agenda desativar`
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy                          # strict em src/ (configurado no pyproject)
```

## Testes

- Todos offline: dublês das portas, SQLite em memória, keyring em memória e `PEAO_DADOS`
  temporário (o `conftest.py` prepara isso **antes** de importar o projeto).
- **Unidade × integração** pelo marcador `integracao` (`--strict-markers`: nome errado falha).
  Integração = componente real fora do Python: Chromium do Playwright (todo teste com a fixture
  `page` é marcado sozinho no `conftest.py`), janela Tk (`test_ui_app.py` inteiro), outro
  processo (trava entre processos) e o PowerShell. O resto é unidade (~5 s).
- **CI** em `.github/workflows/ci.yml`, em todo PR e push na `main`: `lint` (ruff + mypy, Linux;
  o mypy é fixado em `platform = "win32"` para não depender do runner), `unidade` e
  `integracao` (Windows; instala o Chromium com cache pela hash do `uv.lock`). Tudo com
  `uv sync --locked`: `uv.lock` desatualizado quebra o CI de propósito.
- **`--capture=sys` no `pyproject.toml` é obrigatório.** A captura padrão do pytest (fd) troca os
  handles de stdout/stderr do processo a cada fase; o Tcl guarda esses handles e o Windows recicla
  os valores, então a janela do teste seguinte falhava ao ler os próprios arquivos do Tcl
  (`Can't find a usable init.tcl`, `tcl_findLibrary`), ao acaso. Fora do pytest, 40 janelas
  seguidas abrem sem erro.
- Com o app aberto, `uv run` falha ao reinstalar o projeto (`peao-ui.exe` em uso) quando o
  `pyproject.toml` mudou: use `uv run --no-sync ...` ou feche o app.

## Lint e tipagem

- **ruff** com regras além do padrão (bugbear, pyupgrade, async, datas com fuso, `except`
  genérico etc., ver `[tool.ruff.lint]`). Fora de propósito: `E501` (o formatter cuida),
  `RUF001-003` (travessão e aspas tipográficos nos textos em PT-BR), `PT018`. Um `noqa` sempre
  diz o porquê.
- **mypy `--strict` em `src/` e `tests/`**, com o plugin do pydantic (`mypy_path = tests` para
  `dubles`/`construtores`/`consultas`). O CustomTkinter não tem tipos: seus
  widgets são `Any` e as abas podem herdar deles (override só em `peao_bilingue.ui.*`).
- Colunas do SQLModel em `order_by`/`.desc()` passam por `col(...)`, senão o mypy as vê como
  `int | None`/`datetime`.
- Mensagens para os SDKs vão tipadas (`BetaMessageParam`, `ChatCompletionMessageParam`), e
  parâmetro opcional da Anthropic que não deve ir na requisição é `omit` — não `**kwargs`
  montado à parte, que o mypy não consegue conferir. Há teste com o SDK de verdade sobre um
  transporte local (`httpx2`, que o SDK usa) provando que o `omit` não chega à API.

## Auditoria de qualidade (07–08/10, concluída)

Critérios pedidos: arquivos separados por domínio, SOLID, funções tipadas na entrada e na saída.

- [x] `Any` evitável em assinaturas de `src/` (JSON das APIs virou `Json` com checagem do
      formato; callbacks da UI tipados). Sobra só widget do CustomTkinter, sem tipos.
- [x] Raiz de composição respeitada: UI e CLI pegam o repositório em `montar_repositorio()`.
- [x] CLI não importa de `ui/` (textos comuns em `textos.py`).
- [x] Adapter não importa da aplicação: o texto pesquisável da vaga é regra de domínio
      (`Vaga.texto_pesquisavel()`).
- [x] **D** (inversão de dependência): `aplicacao/` não importa mais `configuracao` — o limite
      de detalhes vem em `Servicos.max_detalhes` e as notas do perfil em `notas=`; quem lê
      configuração e arquivo é a composição (`ler_notas_do_perfil`).
- [x] **Domínio em arquivos**: um módulo por subdomínio (vagas, buscas, perfil, análise,
      coleta, avisos, agenda), cada um com suas entidades e portas; `entidades.py` e
      `portas.py` saíram. O domínio não importa nada de fora dele.
- [x] **I/S** (interfaces enxutas, responsabilidade única): cinco portas de repositório, uma
      por agregado; os casos de uso pedem só as que usam (`analisar_vaga(vagas=, perfis=,
      analises=)`, `Servicos(buscas=, vagas=, perfis=, execucoes=)`). `sqlite.py` (434 linhas)
      virou o pacote `persistencia/sqlite/`, um arquivo por agregado (o maior tem 87 linhas).
- [x] Testes tipados: `mypy --strict` agora cobre `src/` **e** `tests/` (343 pendências
      zeradas), inclusive no CI. Restam 4 `type: ignore`, todos comentados (keyring sem tipos,
      nome por instância nos dublês, teste que instancia ABC de propósito).
