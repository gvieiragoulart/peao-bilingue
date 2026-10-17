"""Brazilian Portuguese. Keys are the English text passed to `_()`."""

MESSAGES: dict[str, str] = {
    # --- domain and application --------------------------------------------------
    "Terms can't be just spaces.": "Os termos não podem ser só espaços.",
    "The model refused the analysis: {reason}": "O modelo recusou a análise: {reason}",
    "Invalid answer after {attempts} attempts: {error}": (
        "Resposta inválida após {attempts} tentativas: {error}"
    ),
    "Job {key} not found.": "Vaga {key} não encontrada.",
    "No profile has been read from {source} yet. Read it on the Profile tab, or pick "
    "another source's profile.": (
        "Nenhum perfil da fonte {source} foi lido ainda. Leia na aba Perfil ou escolha "
        "o perfil de outra fonte."
    ),
    "Interrupted: the process ended before finishing (app closed during the "
    "collection, PC turned off or the scheduled task's time limit).": (
        "Interrompida: o processo terminou antes de concluir (app fechado no meio da "
        "coleta, PC desligado ou limite de tempo da tarefa agendada)."
    ),
    "A run is already in progress (in the app or in the scheduled task).": (
        "Já existe uma execução em andamento (no app ou na tarefa agendada)."
    ),
    "Partial failures: {failures}": "Falhas parciais: {failures}",
    "notice via {notifier}: {error}": "aviso por {notifier}: {error}",
    "problem notice via {notifier}: {error}": (
        "aviso do problema por {notifier}: {error}"
    ),
    # --- configuration, factories, shared texts -----------------------------------
    "Unknown setting: {names}": "Configuração desconhecida: {names}",
    "job source": "fonte de vagas",
    "LLM provider": "provedor de LLM",
    "notifier": "notificador",
    "none": "nenhum",
    "Unknown {kind}: {name!r}. Available: {available}.": (
        "{kind} desconhecido: {name!r}. Disponíveis: {available}."
    ),
    "No collection scheduled.": "Nenhuma coleta agendada.",
    "Every day at {time} (task: {state}).": "Todo dia às {time} (tarefa: {state}).",
    "Next: {when}.": "Próxima: {when}.",
    "Last: {when} ({result}).": "Última: {when} ({result}).",
    "code {code}": "código {code}",
    "ok": "ok",
    # --- command line -------------------------------------------------------------
    "Peão Bilíngue: a job radar.": "Peão Bilíngue: radar de vagas.",
    "The {source!r} source doesn't use a manual login.": (
        "A fonte {source!r} não usa login manual."
    ),
    "log in to a source by hand (opens Chrome)": (
        "login manual numa fonte (abre o Chrome)"
    ),
    "is a source's saved session still valid?": "a sessão salva de uma fonte ainda vale?",
    "show the browser": "mostra o navegador",
    "collect now (no LLM: analysis is requested in the window)": (
        "coleta agora (sem LLM: a análise é pedida na interface)"
    ),
    "only these sources (repeatable)": "limita a estas fontes (repetível)",
    "send the new jobs and problems, like the scheduled collection": (
        "manda as vagas novas e os problemas, como a coleta agendada"
    ),
    "list or add searches": "lista ou cadastra buscas",
    "new search": "nova busca",
    "none = every source": "nenhuma = todas as fontes",
    "daily collection through Windows Task Scheduler": (
        "coleta diária pelo Agendador do Windows"
    ),
    "schedule (or reschedule) the daily collection": (
        "agenda (ou reagenda) a coleta diária"
    ),
    "HH:MM; default: the configured one": "HH:MM; padrão: o da configuração",
    "remove the scheduled task": "remove a tarefa agendada",
    "list the available sources, LLMs and notifiers": (
        "lista fontes, LLMs e notificadores disponíveis"
    ),
    "Sources": "Fontes",
    "LLMs": "LLMs",
    "Notifiers": "Notificadores",
    "Run {id}: {status}, {listed} listed, {new} new.": (
        "Execução {id}: {status} — {listed} listadas, {new} novas."
    ),
    "Evidence in {path}.*": "Evidência em {path}.*",
    "Search {id} created.": "Busca {id} criada.",
    "[{id}] {name}: {keywords} | sources: {sources} | {status}": (
        "[{id}] {name}: {keywords} | fontes: {sources} | {status}"
    ),
    "all": "todas",
    "active": "ativa",
    "inactive": "inativa",
    # --- persistence and scheduling -----------------------------------------------
    "Search {id} not found.": "Busca {id} não encontrada.",
    "Run {id} not found.": "Execução {id} não encontrada.",
    "PowerShell didn't answer within {seconds} s. Try again.": (
        "O PowerShell não respondeu em {seconds} s. Tente de novo."
    ),
    "PowerShell ended with code {code}.": "O PowerShell terminou com código {code}.",
    "Invalid time: {time!r}. Use HH:MM, e.g. 08:00.": (
        "Horário inválido: {time!r}. Use HH:MM, ex.: 08:00."
    ),
    # --- job sources --------------------------------------------------------------
    "{source} refused: too many calls. Try again later.": (
        "{source} recusou por excesso de chamadas. Tente mais tarde."
    ),
    "{source} answered with error {code}.": "{source} respondeu com erro {code}.",
    "{source} is down or there is no network: {error}": (
        "{source} fora do ar ou sem rede: {error}"
    ),
    "{source} answered in an unexpected format.": (
        "{source} respondeu num formato inesperado."
    ),
    "{source} changed its response format (expected {expected}).": (
        "{source} mudou o formato da resposta (esperava {expected})."
    ),
    "an object": "um objeto",
    "a list": "uma lista",
    "(untitled)": "(sem título)",
    "/year": "/ano",
    "/month": "/mês",
    "/week": "/semana",
    "/hour": "/hora",
    "{count} countries": "{count} países",
    "{count} countries, including Brazil": "{count} países, inclui Brazil",
    "Remotive (public API, remote jobs)": "Remotive (API pública, vagas remotas)",
    "Remote OK (public API, remote jobs)": "Remote OK (API pública, vagas remotas)",
    "Arbeitnow (public API, Germany with a visa)": (
        "Arbeitnow (API pública, Alemanha com visto)"
    ),
    "Himalayas (public API, remote jobs)": "Himalayas (API pública, vagas remotas)",
    "We Work Remotely (public RSS, remote jobs)": (
        "We Work Remotely (RSS público, vagas remotas)"
    ),
    # --- VanHack ------------------------------------------------------------------
    "Cloudflare rejected this browser (Security check could not complete)": (
        "Cloudflare recusou este navegador (Security check could not complete)"
    ),
    "Cloudflare human challenge (Turnstile) on the page": (
        "Desafio humano do Cloudflare (Turnstile) presente na página"
    ),
    "Possible human check on the page: {text!r}": (
        "Possível verificação humana na página: {text!r}"
    ),
    "The VanHack session expired. Log in by hand again: “Log in” on the app's "
    "Sources tab, or `peao login` on the command line.": (
        "Sessão da VanHack expirada. Faça o login manual de novo: “Fazer login” na aba "
        "Fontes do app, ou `peao login` na linha de comando."
    ),
    "{reason} (evidence in {path})": "{reason} (evidência em {path})",
    "Log in on the window that just opened.\n\n"
    "  - If you log in by email, VanHack sends a link. DON'T click the link in\n"
    "    your email client: copy the address and paste it in this window's\n"
    "    address bar, or the session ends up in the wrong browser and nothing\n"
    "    is saved here.\n"
    "  - Logging in with Google or LinkedIn works too, as long as it happens in\n"
    "    this window.\n"
    '  - The "confirm you are human" check is yours: the robot never solves it.\n\n'
    "As soon as the VanHack dashboard loads, the session is saved automatically.\n"
    "Waiting up to 10 minutes...": (
        "Faça o login na janela que acabou de abrir.\n\n"
        "  - Se escolher entrar por email, a VanHack manda um link. NÃO clique no link\n"
        "    pelo seu cliente de email: copie o endereço e cole na barra desta janela,\n"
        "    senão a sessão fica no navegador errado e nada é salvo aqui.\n"
        "  - Login por Google ou LinkedIn também funciona, desde que feito nesta janela.\n"
        '  - A verificação "confirme que é humano" é sua: o robô nunca a resolve.\n\n'
        "Assim que o painel da VanHack carregar, a sessão é salva automaticamente.\n"
        "Aguardando até 10 minutos..."
    ),
    "The session was already valid. Saved in {path}.": (
        "A sessão já estava válida. Salva em {path}."
    ),
    "Timed out without a login. Evidence in {path}.*": (
        "Tempo esgotado sem login. Evidência em {path}.*"
    ),
    "The login didn't finish. Evidence in {path}.*": (
        "O login não completou. Evidência em {path}.*"
    ),
    "Logged in. Session saved in {path}.": "Login concluído. Sessão salva em {path}.",
    "No saved session. Log in first: “Log in” on the Sources tab, or `peao login`.": (
        "Nenhuma sessão salva. Faça o login primeiro: “Fazer login” na aba Fontes, ou "
        "`peao login`."
    ),
    "[profile] blocked: {reason}. Evidence in {path}.*": (
        "[perfil] bloqueado: {reason}. Evidência em {path}.*"
    ),
    "[profile] no session (redirected to the login). Evidence in {path}.*": (
        "[perfil] sem sessão (redirecionou para o login). Evidência em {path}.*"
    ),
    "[profile] OK: {url} — {title}": "[perfil] OK: {url} — {title}",
    "[jobs] blocked: {reason}. Evidence in {path}.*": (
        "[vagas] bloqueado: {reason}. Evidência em {path}.*"
    ),
    "[jobs] OK: {url} — {title}": "[vagas] OK: {url} — {title}",
    "Valid session, and the pages open under Playwright.": (
        "Sessão válida e páginas acessíveis pelo Playwright."
    ),
    # --- LLM providers ------------------------------------------------------------
    "Model": "Modelo",
    "Model (required)": "Modelo (obrigatório)",
    "API key": "Chave da API",
    "Ollama (local, free)": "Ollama (local, grátis)",
    "Address": "Endereço",
    "Context (tokens)": "Contexto (tokens)",
    "Ollama isn't running at {host}. Open the Ollama app or run `ollama serve`.": (
        "O Ollama não está rodando em {host}. Abra o app do Ollama ou rode "
        "`ollama serve`."
    ),
    "The {model!r} model isn't downloaded. Run `ollama pull {model}`.": (
        "O modelo {model!r} não está baixado. Rode `ollama pull {model}`."
    ),
    "Choose the OpenAI model on the LLMs tab. There is no default: OpenAI's catalog "
    "changes.": (
        "Escolha o modelo da OpenAI na aba LLMs. Não há padrão: o catálogo da OpenAI "
        "muda."
    ),
    "Fill in the OpenAI API key on the LLMs tab.": (
        "Preencha a chave da API da OpenAI na aba LLMs."
    ),
    "Choose the Gemini model on the LLMs tab. There is no default: Gemini's catalog "
    "changes.": (
        "Escolha o modelo do Gemini na aba LLMs. Não há padrão: o catálogo do Gemini "
        "muda."
    ),
    "Fill in the Gemini API key on the LLMs tab.": (
        "Preencha a chave da API do Gemini na aba LLMs."
    ),
    "prompt blocked: {reason}": "prompt bloqueado: {reason}",
    "answer blocked: {reason}": "resposta bloqueada: {reason}",
    # --- notices ------------------------------------------------------------------
    "Email (new jobs and problems)": "Email (vagas novas e problemas)",
    "SMTP server": "Servidor SMTP",
    "Port": "Porta",
    "User": "Usuário",
    "Password": "Senha",
    "Send to": "Enviar para",
    "WhatsApp through Twilio (new jobs and problems)": (
        "WhatsApp via Twilio (vagas novas e problemas)"
    ),
    "Sender number": "Número de origem",
    "Peão Bilíngue — {count} new job(s)": "Peão Bilíngue — {count} vaga(s) nova(s)",
    "Open the app to analyze the ones you're interested in.": (
        "Abra o app para analisar as que interessarem."
    ),
    "+{count} job(s) in the app": "+{count} vaga(s) no app",
    "Peão Bilíngue — the collection needs attention": (
        "Peão Bilíngue — a coleta precisa de atenção"
    ),
    "The scheduled collection couldn't read everything:": (
        "A coleta agendada não conseguiu ler tudo:"
    ),
    "The details are on the app's Runs tab.": "Os detalhes ficam na aba Execuções do app.",
    # --- window: shared -----------------------------------------------------------
    "{app} — job radar": "{app} — radar de vagas",
    "Jobs": "Vagas",
    "Searches": "Buscas",
    "Profile": "Perfil",
    "Runs": "Execuções",
    "Settings": "Configurações",
    "All": "Todas",
    "New": "Nova",
    "Studying": "Estudando",
    "Applied": "Aplicada",
    "Discarded": "Descartada",
    "running": "rodando",
    "error": "erro",
    "login required": "login necessário",
    "manual": "manual",
    "scheduled": "agendada",
    "yes": "sim",
    "no": "não",
    "Save": "Salvar",
    "Status": "Status",
    "Source": "Fonte",
    "Search": "Busca",
    "Checking…": "Verificando…",
    "'{field}' must be a whole number.": "'{field}' precisa ser um número inteiro.",
    # --- window: job detail -------------------------------------------------------
    "Also on {source}: {url}": "Também em {source}: {url}",
    "Fit: {score}/100": "Fit: {score}/100",
    "SUMMARY": "RESUMO",
    "PREPARATION": "PREPARAÇÃO",
    "INTERVIEW QUESTIONS ({count})": "PERGUNTAS DE ENTREVISTA ({count})",
    "GAPS": "GAPS",
    "(none found)": "(nenhum identificado)",
    "WHAT TO IMPROVE IN THE PROFILE": "O QUE MELHORAR NO PERFIL",
    "Not analyzed yet: pick the LLM and the profile, then click Analyze.": (
        "Ainda não analisada: escolha o LLM e o perfil e clique em Analisar."
    ),
    "DESCRIPTION": "DESCRIÇÃO",
    "(no description)": "(sem descrição)",
    "Analysis by {provider} ({model}) on {when}": (
        "Análise por {provider} ({model}) em {when}"
    ),
    ", with the {source} profile": ", com o perfil da fonte {source}",
    "The {source} profile changed after this analysis: analyze again to update it.": (
        "O perfil da fonte {source} mudou depois desta análise: analise de novo para "
        "atualizar."
    ),
    "The minimum fit must be a number from 0 to 100.": (
        "O fit mínimo precisa ser um número de 0 a 100."
    ),
    # --- window: Jobs tab ---------------------------------------------------------
    "(none)": "(nenhum)",
    "Search the title, company, location, skills and description (Enter to filter)": (
        "Procurar no título, empresa, local, skills e descrição (Enter para filtrar)"
    ),
    "fit ≥": "fit ≥",
    "Minimum fit": "Fit mínimo",
    "Filter": "Filtrar",
    "Fit": "Fit",
    "Job": "Vaga",
    "Location": "Local",
    "Analyze": "Analisar",
    "Open job": "Abrir vaga",
    "Mark as:": "Marcar como:",
    "{count} job(s). Pick one to see its analysis or to analyze it.": (
        "{count} vaga(s). Selecione uma para ver a análise ou analisar."
    ),
    "Pick a job to analyze.": "Selecione uma vaga para analisar.",
    "Analyzing…": "Analisando…",
    "Analyzing {title} ({key}) with {llm}…": "Analisando {title} ({key}) com {llm}…",
    "Analysis ready: {title} — fit {score}.": "Análise pronta: {title} — fit {score}.",
    # --- window: Searches tab -----------------------------------------------------
    "Name": "Nome",
    "Keywords": "Palavras-chave",
    "Exclude": "Excluir",
    "Active": "Ativa",
    "New search": "Nova busca",
    "Keywords (comma separated)": "Palavras-chave (separadas por vírgula)",
    "Exclude when present (optional)": "Excluir se aparecer (opcional)",
    'Careful: "junior" also matches "mentor junior engineers".': (
        'Cuidado: "junior" também casa com "mentor junior engineers".'
    ),
    "Sources (none checked = all)": "Fontes (nenhuma marcada = todas)",
    "Remove": "Remover",
    "Editing: {name}": "Editando: {name}",
    "Give it a name and at least one keyword.": (
        "Dê um nome e ao menos uma palavra-chave."
    ),
    # --- window: Sources tab ------------------------------------------------------
    "Enabled sources take part in the collection. Those that need an account use a "
    "manual login: the robot never fills in a login form or solves a human check.": (
        "Fontes ligadas entram na coleta. As que exigem conta usam login manual: o robô "
        "nunca preenche o login nem resolve verificação humana."
    ),
    "browser": "navegador",
    "reads your profile": "lê o seu perfil",
    "Check session": "Verificar sessão",
    "Log in": "Fazer login",
    "Valid session": "Sessão válida",
    "No session: log in": "Sem sessão: faça o login",
    "Blocked by a human check": "Bloqueado por verificação humana",
    "Login window open: follow the steps in the log": (
        "Janela de login aberta: siga as instruções no registro"
    ),
    "Login not finished": "Login não concluído",
    "Logged in": "Login concluído",
    # --- window: LLMs tab ---------------------------------------------------------
    "Who analyzes": "Quem analisa",
    "The collection calls no LLM: analysis is requested job by job, on the Jobs tab, "
    "with the LLM picked there. The default below is the one already selected.": (
        "A coleta não chama LLM nenhum: a análise é pedida vaga a vaga, na aba Vagas, "
        "com o LLM escolhido lá. O padrão abaixo é o que já vem selecionado."
    ),
    "Default LLM": "LLM padrão",
    "The keys live in Windows Credential Manager, not in a file.": (
        "As chaves ficam no Cofre de Credenciais do Windows, não em arquivo."
    ),
    "LLM settings saved.": "Configuração dos LLMs salva.",
    # --- window: Profile tab ------------------------------------------------------
    "Read profile now": "Ler perfil agora",
    "Reading…": "Lendo…",
    "Read on": "Lido em",
    "What changed": "O que mudou",
    "No enabled source reads a profile.": "Nenhuma fonte ligada lê perfil.",
    "No {source} profile read yet.": "Nenhum perfil da fonte {source} lido ainda.",
    "Click Read profile now.": "Clique em Ler perfil agora.",
    "The {source} profile, used to analyze its jobs (no personal data):": (
        "Perfil da fonte {source}, usado nas análises das vagas dela (sem dados "
        "pessoais):"
    ),
    "The {source} source is off or doesn't read a profile.": (
        "A fonte {source} não está ligada ou não lê perfil."
    ),
    "The {source} profile was updated.": "Perfil da fonte {source} atualizado.",
    "The profile hasn't changed.": "Perfil sem mudanças.",
    # --- window: Runs tab ---------------------------------------------------------
    "The collection looks for new jobs and saves them, with no LLM: analyze the ones "
    "you want on the Jobs tab.": (
        "A coleta busca e guarda as vagas novas, sem chamar LLM: analise as que quiser "
        "na aba Vagas."
    ),
    "Collect now": "Coletar agora",
    "Collecting…": "Coletando…",
    "Collection started.": "Coleta iniciada.",
    "Collection {status}: {listed} listed, {new} new.": (
        "Coleta {status}: {listed} listada(s), {new} nova(s)."
    ),
    "Daily automatic collection": "Coleta diária automática",
    "Schedule": "Agendar",
    "Cancel": "Cancelar",
    "Scheduling…": "Agendando…",
    "Cancelling…": "Cancelando…",
    "Couldn't read the schedule: {error}": "Não consegui consultar a agenda: {error}",
    "Start": "Início",
    "Trigger": "Gatilho",
    "Listed": "Listadas",
    "Error": "Erro",
    "Log": "Registro",
    # --- window: Settings tab -----------------------------------------------------
    "Collection limits": "Limites da coleta",
    "Jobs detailed per source, per run": "Vagas detalhadas por fonte, por execução",
    "Maximum listing scrolls": "Rolagens máximas da listagem",
    "Hide the browser during the collection": "Navegador escondido durante a coleta",
    "Profile notes file": "Arquivo de notas do perfil",
    "Notices": "Avisos",
    "After the scheduled collection, a digest of the new jobs (title, source and "
    "link) through the enabled channels, and a notice if something fails, like a "
    "source's expired session. Only turn on the ones already filled in.": (
        "Depois da coleta agendada, um resumo das vagas novas (título, fonte e link) "
        "pelos canais ligados, e um aviso se algo falhar, como a sessão de uma fonte "
        "vencida. Ligue só os que já estiverem preenchidos."
    ),
    "Settings saved.": "Configurações salvas.",
}
