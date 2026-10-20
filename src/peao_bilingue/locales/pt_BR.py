"""Brazilian Portuguese. Keys are the English text passed to `_()`."""

MESSAGES: dict[str, str] = {
    # --- domain and application --------------------------------------------------
    "Terms can't be just spaces.": "Os termos não podem ser só espaços.",
    "The model refused the analysis: {reason}": "O modelo recusou a análise: {reason}",
    "Invalid answer after {attempts} attempts: {error}": (
        "Resposta inválida após {attempts} tentativas: {error}"
    ),
    "Job {key} not found.": "Vaga {key} não encontrada.",
    "There's no profile to compare this job with. On the Profile tab, paste your CV or "
    "read the profile of a source like VanHack.": (
        "Não há perfil para comparar com esta vaga. Na aba Perfil, cole o seu currículo "
        "ou leia o perfil de uma fonte como a VanHack."
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
    "save a screenshot + HTML of each search on sources that read web pages": (
        "salva print + HTML de cada pesquisa nas fontes que leem páginas web"
    ),
    "Screenshots saved in {path}.": "Prints salvos em {path}.",
    "No screenshots: no source in this collection reads web pages.": (
        "Nenhum print: nenhuma fonte desta coleta lê páginas web."
    ),
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
    # --- Each source: its card, its dialog and its settings -----------------------
    "Senior tech jobs at companies that sponsor visas and relocation, plus remote "
    "jobs with companies that hire internationally. Uses your account.": (
        "Vagas sênior de tecnologia em empresas que patrocinam visto e mudança, e "
        "vagas remotas em empresas que contratam de fora. Usa a sua conta."
    ),
    "The robot reads the jobs and your VanHack profile with the session saved when "
    "you log in by hand: it never fills in the login form or solves a human check. "
    "If the session expires, the collection stops and asks you to log in again.": (
        "O robô lê as vagas e o seu perfil na VanHack com a sessão salva quando você "
        "faz o login à mão: ele nunca preenche o formulário de login nem resolve uma "
        "verificação humana. Se a sessão expirar, a coleta para e pede um novo login."
    ),
    "Fully remote jobs from vetted companies, here in software development. Public "
    "API, no account.": (
        "Vagas 100% remotas de empresas verificadas, aqui em desenvolvimento de "
        "software. API pública, sem conta."
    ),
    "Remotive's free API has the jobs 24 h late and asks for no more than a few "
    "calls a day, so the app makes one call per collection and keeps the answer for "
    "6 hours. Each job links back to Remotive, as its terms ask.": (
        "A API gratuita do Remotive traz as vagas com 24 h de atraso e pede poucas "
        "chamadas por dia: o app faz uma chamada por coleta e guarda a resposta por 6 "
        "horas. Cada vaga leva de volta ao Remotive, como pedem os termos."
    ),
    "One of the biggest remote job boards, with open salaries: the ~100 latest "
    "remote jobs from every field. Public API, no account.": (
        "Um dos maiores sites de vagas remotas, com salários abertos: as ~100 vagas "
        "remotas mais recentes de todas as áreas. API pública, sem conta."
    ),
    "One call per collection, kept for 6 hours. The API brings a shortened "
    "description; the full text is on the site. Each job links back to Remote OK, "
    "as its terms ask.": (
        "Uma chamada por coleta, guardada por 6 horas. A API traz a descrição "
        "resumida; o texto completo fica no site. Cada vaga leva de volta ao Remote "
        "OK, como pedem os termos."
    ),
    "Jobs in Germany with visa sponsorship, many in English with no German "
    "required: a path to relocation. Public API, no account.": (
        "Vagas na Alemanha com patrocínio de visto, muitas em inglês e sem exigir "
        "alemão: um caminho para a mudança. API pública, sem conta."
    ),
    "Only jobs with visa sponsorship come in, in one call per collection, kept for "
    "6 hours. Some are still written in German. Each job links back to Arbeitnow, "
    "as its terms ask.": (
        "Só entram as vagas com patrocínio de visto, numa chamada por coleta, "
        "guardada por 6 horas. Algumas ainda estão em alemão. Cada vaga leva de volta "
        "ao Arbeitnow, como pedem os termos."
    ),
    "A leading remote job board; here, only the jobs open to Brazil or worldwide. "
    "Public API, no account.": (
        "Um dos principais sites de vagas remotas; aqui, só as vagas abertas ao "
        "Brasil ou ao mundo todo. API pública, sem conta."
    ),
    "Searched once per keyword of your searches (up to 20 jobs each), with a 2 s "
    "pause between calls, each answer kept for 12 hours. The country is an ISO code "
    "(BR); empty brings jobs for every country, US-only ones included. Each job "
    "links back to Himalayas.": (
        "Buscado uma vez por palavra-chave das suas buscas (até 20 vagas cada), com "
        "uma pausa de 2 s entre as chamadas, cada resposta guardada por 12 horas. O "
        "país é um código ISO (BR); vazio traz vagas de todos os países, inclusive as "
        "só para os EUA. Cada vaga leva de volta à Himalayas."
    ),
    "The largest remote work community in the world, since 2013: back-end, "
    "full-stack and front-end jobs from its RSS feeds. No account.": (
        "A maior comunidade de trabalho remoto do mundo, desde 2013: vagas de "
        "back-end, full-stack e front-end dos seus feeds RSS. Sem conta."
    ),
    "Three feeds per collection, one per category, with a 2 s pause, kept for 6 "
    "hours. Each job links back to We Work Remotely, as the feed page asks.": (
        "Três feeds por coleta, um por categoria, com uma pausa de 2 s, guardados por "
        "6 horas. Cada vaga leva de volta ao We Work Remotely, como pede a página dos "
        "feeds."
    ),
    "Remote jobs at US companies, 100% remote for Latin America. Reads the public "
    "jobs page; no account needed.": (
        "Vagas remotas em empresas dos EUA, 100% remotas para a América Latina. Lê a "
        "página pública de vagas; não precisa de conta."
    ),
    "Strider matches candidates itself and its app has no job list, so only the "
    "public jobs page is read: once per collection, then each new job's page with a "
    "2-5 s pause. The company is never named. Each job keeps its Strider link.": (
        "A Strider escolhe os candidatos ela mesma e o app dela não tem lista de "
        "vagas, então só a página pública é lida: uma vez por coleta e depois a "
        "página de cada vaga nova, com uma pausa de 2 a 5 s. A empresa nunca é "
        "nomeada. Cada vaga guarda o seu link da Strider."
    ),
    "A global remote job board: jobs open to Brazil, Latin America or anywhere, "
    "from the last 7 days. Public API, no account.": (
        "Um site global de vagas remotas: vagas abertas ao Brasil, à América Latina "
        "ou ao mundo todo, dos últimos 7 dias. API pública, sem conta."
    ),
    "One call per collection, kept for 6 hours. The region is Jobicy's geo filter: "
    '"brazil" already includes the Latin America and anywhere jobs. Each job links '
    "back to Jobicy, as its terms ask.": (
        "Uma chamada por coleta, guardada por 6 horas. A região é o filtro geo do "
        'Jobicy: "brazil" já inclui as vagas da América Latina e do mundo todo. Cada '
        "vaga leva de volta ao Jobicy, como pedem os termos."
    ),
    "The biggest tech and startup jobs community in Latin America; here, only the "
    "fully remote jobs. Public API, no account.": (
        "A maior comunidade de vagas de tecnologia e startups da América Latina; "
        "aqui, só as vagas 100% remotas. API pública, sem conta."
    ),
    "Searched once per keyword of your searches, with a 2 s pause between calls, "
    "each answer kept for 12 hours. Most jobs there are on-site or remote within "
    "one country (Chile, mostly): only the fully remote ones come in.": (
        "Buscado uma vez por palavra-chave das suas buscas, com uma pausa de 2 s "
        "entre as chamadas, cada resposta guardada por 12 horas. Lá, a maioria das "
        "vagas é presencial ou remota dentro de um país (o Chile, quase sempre): só "
        "entram as 100% remotas."
    ),
    "GitHub job repositories": "Vagas no GitHub",
    "Brazilian developer communities that post jobs as GitHub issues, tagged by "
    "seniority, contract and technology (backend-br/vagas and others). Public API, "
    "no account.": (
        "Comunidades brasileiras de desenvolvimento que publicam vagas como issues no "
        "GitHub, com etiquetas de senioridade, contrato e tecnologia "
        "(backend-br/vagas e outros). API pública, sem conta."
    ),
    "One call per repository per collection, with a 1 s pause, kept for 6 hours: "
    "GitHub allows 60 calls an hour without an account. One repository per line, as "
    "owner/repo. Recruiters' emails, phones and links are removed from each job.": (
        "Uma chamada por repositório por coleta, com uma pausa de 1 s, guardada por 6 "
        "horas: sem conta, o GitHub permite 60 chamadas por hora. Um repositório por "
        "linha, como dono/repo. Os emails, telefones e links dos recrutadores são "
        "tirados de cada vaga."
    ),
    "Company job boards": "Vagas direto das empresas",
    "Jobs straight from the careers pages of companies that hire in Brazil or "
    "remotely in Latin America (Nubank, Stone, QuintoAndar...), through the "
    "Greenhouse, Lever and Ashby APIs. No account.": (
        "Vagas direto das páginas de carreira de empresas que contratam no Brasil ou "
        "remoto na América Latina (Nubank, Stone, QuintoAndar...), pelas APIs do "
        "Greenhouse, do Lever e do Ashby. Sem conta."
    ),
    "One call per board per collection, with a 1 s pause, kept for 6 hours. One "
    "board per line, as ats:board=Company: the system (greenhouse, lever or ashby), "
    "the board's name as in its address and, if you like, the company's name. A "
    "job stays only when its location names one of the places (one per line, "
    "without accents); no place keeps them all.": (
        "Uma chamada por página por coleta, com uma pausa de 1 s, guardada por 6 "
        "horas. Uma página por linha, como ats:pagina=Empresa: o sistema (greenhouse, "
        "lever ou ashby), o nome da página como no endereço e, se quiser, o nome da "
        "empresa. Uma vaga só fica quando o local dela cita um dos lugares (um por "
        "linha, sem acentos); sem nenhum lugar, ficam todas."
    ),
    "The monthly thread where companies post jobs on Hacker News; only posts open "
    "to Brazil, Latin America or anywhere. No account.": (
        "O tópico mensal em que empresas publicam vagas no Hacker News; só os "
        "anúncios abertos ao Brasil, à América Latina ou ao mundo todo. Sem conta."
    ),
    "Two calls per collection, through the HN Search API by Algolia: one finds the "
    "newest thread, the other brings it whole; kept for 12 hours. A post stays only "
    "when it names one of the places (one per line, without accents). Not visa: as "
    "many posts say they cannot sponsor one as offer it.": (
        "Duas chamadas por coleta, pela HN Search API da Algolia: uma acha o tópico "
        "mais recente, a outra o traz inteiro; guardadas por 12 horas. Um anúncio só "
        "fica quando cita um dos lugares (um por linha, sem acentos). Sem visa: "
        "tantos anúncios dizem que não patrocinam visto quanto os que oferecem."
    ),
    "Category": "Categoria",
    "Country (ISO code)": "País (código ISO)",
    "Region": "Região",
    "Repositories": "Repositórios",
    "Boards": "Páginas",
    "Places": "Lugares",
    "the job's requirements": "os requisitos da vaga",
    "company boards": "páginas das empresas",
    "USD {amount}/month": "USD {amount}/mês",
    "Hacker News: no Who is hiring? thread found.": (
        "Hacker News: nenhum tópico Who is hiring? encontrado."
    ),
    "Invalid company board {entry!r}: use greenhouse:, lever: or ashby: followed by "
    "the board's name.": (
        "Página de empresa inválida {entry!r}: use greenhouse:, lever: ou ashby: "
        "seguido do nome da página."
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
    "Windows notification (new jobs and problems)": (
        "Notificação do Windows (vagas novas e problemas)"
    ),
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
    "Version {version} of {app} is available.": (
        "A versão {version} do {app} está disponível."
    ),
    "Download": "Baixar",
    "Later": "Depois",
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
    "(none found)": "(nenhum identificado)",
    "Not analyzed yet: pick the LLM and the profile, then click Analyze.": (
        "Ainda não analisada: escolha o LLM e o perfil e clique em Analisar."
    ),
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
    "Found {found} · published at the source {published}.": (
        "Encontrada {found} · publicada na fonte {published}."
    ),
    "Found {found} · the source doesn't give the publication date.": (
        "Encontrada {found} · a fonte não informa a data de publicação."
    ),
    "{mark} New at the source: published at most {days} days before we found it.": (
        "{mark} Nova na fonte: publicada até {days} dias antes de a encontrarmos."
    ),
    # --- window: how long ago -----------------------------------------------------
    "today": "hoje",
    "yesterday": "ontem",
    "{days} d ago": "há {days} d",
    "1 month ago": "há 1 mês",
    "{months} months ago": "há {months} meses",
    "1 year ago": "há 1 ano",
    "{years} years ago": "há {years} anos",
    # --- window: Jobs tab ---------------------------------------------------------
    "(none)": "(nenhum)",
    "fit ≥": "fit ≥",
    "Minimum fit": "Fit mínimo",
    "Fit": "Fit",
    "Job": "Vaga",
    "Published": "Publicada",
    "Analyze": "Analisar",
    "Open job": "Abrir vaga",
    "Mark as:": "Marcar como:",
    "found {when}": "encontrada {when}",
    "Mark as…": "Marcar como…",
    "{count} job(s) marked as {status}.": "{count} vaga(s) marcada(s) como {status}.",
    "Job discarded.": "Vaga descartada.",
    "Delete for good": "Excluir de vez",
    "Delete {count} job(s) for good? This can't be undone; if a source still lists a "
    "job, it comes back on the next collection.": (
        "Excluir {count} vaga(s) de vez? Não dá para desfazer; se uma fonte ainda "
        "publicar a vaga, ela volta na próxima coleta."
    ),
    "{count} job(s) deleted.": "{count} vaga(s) excluída(s).",
    "Undo": "Desfazer",
    # --- LLMs: cards and modal ---------------------------------------------------------
    "Claude, Anthropic's models, through its API. Paid per use, with your API key.": (
        "Claude, os modelos da Anthropic, pela API dela. Pago por uso, com a sua chave "
        "de API."
    ),
    "The app sends the job and your profile, without contact data, only when you "
    "click Analyze on a job.": (
        "O app envia a vaga e o seu perfil, sem dados de contato, só quando você clica "
        "em Analisar numa vaga."
    ),
    "OpenAI's GPT models through its API. Paid per use: needs your API key and a "
    "model name.": (
        "Os modelos GPT da OpenAI, pela API dela. Pago por uso: precisa da sua chave de "
        "API e do nome de um modelo."
    ),
    "The app sends the job and your profile, without contact data, only when you "
    "click Analyze on a job. There is no default model: the catalog changes, so "
    "write the one your key can use.": (
        "O app envia a vaga e o seu perfil, sem dados de contato, só quando você clica "
        "em Analisar numa vaga. Não há modelo padrão: o catálogo muda, então escreva um "
        "que a sua chave possa usar."
    ),
    "Google's Gemini models through the Gemini API. Needs your API key and a model "
    "name.": (
        "Os modelos Gemini do Google, pela API do Gemini. Precisa da sua chave de API e "
        "do nome de um modelo."
    ),
    "Open models running on this PC through Ollama. Free, and nothing leaves the "
    "computer.": (
        "Modelos abertos rodando neste PC pelo Ollama. De graça, e nada sai do "
        "computador."
    ),
    "Install Ollama, start it (ollama serve) and download a model (ollama pull). "
    "On a 6 GB GPU, quantized 7–8B models fit. The app always sets the context "
    "size: Ollama's small default would cut the prompt without saying so.": (
        "Instale o Ollama, inicie (ollama serve) e baixe um modelo (ollama pull). Numa "
        "GPU de 6 GB cabem modelos 7–8B quantizados. O app sempre define o tamanho do "
        "contexto: o padrão pequeno do Ollama cortaria o prompt sem avisar."
    ),
    "Default": "Padrão",
    "Configure the LLMs you want to use to analyze jobs; which one is picked by "
    "default is in Settings.": (
        "Configure os LLMs que você quer usar para analisar vagas; qual vem escolhido "
        "por padrão fica em Configurações."
    ),
    "Each LLM's key and model are on the LLMs tab.": (
        "A chave e o modelo de cada LLM ficam na aba LLMs."
    ),
    "Good fit": "Bom encaixe",
    "Worth a look": "Vale olhar",
    "Weak fit": "Encaixe fraco",
    "Preparation": "Preparação",
    "Questions ({count})": "Perguntas ({count})",
    "Gaps ({count})": "Lacunas ({count})",
    "Improve the profile": "Melhorar o perfil",
    "Discard": "Descartar",
    "Clear": "Limpar",
    "Search the title, company, skills and description": (
        "Buscar no título, empresa, skills e descrição"
    ),
    "{count} selected": "{count} selecionada(s)",
    "Discard {count} job(s)?": "Descartar {count} vaga(s)?",
    "No keyword from the searches shows up in this job anymore.": (
        "Nenhuma palavra-chave das buscas aparece mais nesta vaga."
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
    "no account needed": "sem conta",
    "Configure": "Configurar",
    "Open the site": "Abrir o site",
    "Session": "Sessão",
    "Close": "Fechar",
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
    "My CV (pasted)": "Meu currículo (colado)",
    "Save profile": "Salvar perfil",
    "Import file…": "Importar arquivo…",
    "Import your CV": "Importar o seu currículo",
    "CV or profile": "Currículo ou perfil",
    "Paste your CV or profile (or import a file) and save. It's the profile for jobs "
    "whose source has none. Emails, phones and links are removed automatically.": (
        "Cole o seu currículo ou perfil (ou importe um arquivo) e salve. É o perfil das "
        "vagas de fontes que não têm um. Emails, telefones e links saem sozinhos."
    ),
    "Paste your CV or profile first.": "Cole o seu currículo ou perfil primeiro.",
    "No text found in the file (a scanned PDF is an image). Paste the text instead.": (
        "Nenhum texto no arquivo (PDF escaneado é imagem). Cole o texto no lugar."
    ),
    "Imported. Check the text and click Save profile.": (
        "Importado. Confira o texto e clique em Salvar perfil."
    ),
    "Can't read {name}: use a .txt, .md or .pdf file.": (
        "Não consigo ler {name}: use um arquivo .txt, .md ou .pdf."
    ),
    "Notes about you": "Notas sobre você",
    "Save notes": "Salvar notas",
    "They go into every analysis, with any profile: what you want and don't want, and "
    'what the profile doesn\'t show (e.g. "I want remote jobs only", "I\'ve led a team '
    'of 5").': (
        "Entram em toda análise, com qualquer perfil: o que você quer e não quer, e o "
        'que o perfil não mostra (ex.: "quero só vagas remotas", "já liderei um time '
        'de 5").'
    ),
    "Saved.": "Salvo.",
    "Saved. Removed from the text: {items}.": "Salvo. Saíram do texto: {items}.",
    "Also check that your name, address and documents aren't in it.": (
        "Confira também se não ficaram o seu nome, endereço ou documentos."
    ),
    "{count} email(s)": "{count} email(s)",
    "{count} phone number(s)": "{count} telefone(s)",
    "{count} link(s)": "{count} link(s)",
    "{count} CPF number(s)": "{count} CPF(s)",
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
    "Collection started: {source}.": "Coleta iniciada: {source}.",
    "All enabled sources": "Todas as fontes ativas",
    "Save a screenshot of each search": "Salvar print de cada pesquisa",
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
    "Appearance": "Aparência",
    "job radar": "radar de vagas",
    "No daily collection": "Sem coleta diária",
    "Daily collection at {time}": "Coleta diária às {time}",
    "No collection yet": "Nenhuma coleta ainda",
    "Collecting since {when}": "Coletando desde {when}",
    "Last: {when} · {status}": "Última: {when} · {status}",
    "Last: {when} · {count} new": "Última: {when} · {count} novas",
    "Same as Windows": "Igual ao Windows",
    "Light": "Claro",
    "Dark": "Escuro",
    "About and support": "Sobre e suporte",
    "Version {version}": "Versão {version}",
    "Check for a new version when the app opens": (
        "Procurar versão nova ao abrir o app"
    ),
    "Open the logs folder": "Abrir pasta de registros",
    "Project page": "Página do projeto",
    # The first-run guide
    "Run the setup guide again": "Abrir o guia de configuração de novo",
    "Skip the guide": "Pular o guia",
    "Next": "Avançar",
    "Back": "Voltar",
    "Finish": "Concluir",
    "Step {number} of {total}": "Passo {number} de {total}",
    "Welcome": "Boas-vindas",
    "What are you looking for?": "O que você procura?",
    "Where to look": "Onde procurar",
    "Your profile": "Seu perfil",
    "Who analyzes the jobs": "Quem analisa as vagas",
    "Collection and notices": "Coleta e avisos",
    "{app} collects jobs from several sites every day, keeps the ones that match your "
    "searches and tells you about the new ones. When a job interests you, an LLM "
    "compares it with your profile: a fit score, what to prepare and 20 interview "
    "questions.": (
        "O {app} coleta vagas de vários sites todo dia, guarda as que batem com as suas "
        "buscas e avisa das novas. Quando uma vaga interessar, um LLM compara a vaga com "
        "o seu perfil: nota de aderência, o que estudar e 20 perguntas de entrevista."
    ),
    "How your data is treated": "Como seus dados são tratados",
    "Everything stays on this computer: the jobs, your profile and the settings. Keys "
    "and passwords go to Windows Credential Manager.": (
        "Tudo fica neste computador: as vagas, o seu perfil e as configurações. Chaves e "
        "senhas vão para o Gerenciador de Credenciais do Windows."
    ),
    "The collection calls no LLM. Your profile only goes to the LLM you pick, when you "
    "click Analyze on a job.": (
        "A coleta não chama nenhum LLM. O seu perfil só vai para o LLM que você escolher, "
        "quando clicar em Analisar numa vaga."
    ),
    "Emails, phone numbers and links are removed from your CV before it's saved.": (
        "Emails, telefones e links são tirados do seu currículo antes de salvar."
    ),
    "Sites that need an account use your own manual login: the app never types a "
    "password or solves a human check.": (
        "Sites que pedem conta usam o seu próprio login, feito à mão: o app nunca digita "
        "senha nem resolve verificação humana."
    ),
    "It takes about 3 minutes, and everything can be changed later.": (
        "Leva uns 3 minutos, e tudo pode ser mudado depois."
    ),
    "Jobs whose title, skills or description have one of the keywords are kept. You can "
    "add more searches later, on the Searches tab.": (
        "Ficam as vagas com alguma das palavras-chave no título, nas habilidades ou na "
        "descrição. Dá para criar mais buscas depois, na aba Buscas."
    ),
    "e.g. python, django, backend": "ex.: python, django, backend",
    "e.g. intern, wordpress": "ex.: estágio, wordpress",
    "Name (optional)": "Nome (opcional)",
    "e.g. Python backend": "ex.: Backend Python",
    "Give it at least one keyword, or leave the search blank.": (
        "Coloque pelo menos uma palavra-chave, ou deixe a busca em branco."
    ),
    "Public APIs need no account. Sites with a login use yours: after the guide, log in "
    "on the Sources tab.": (
        "As APIs públicas não pedem conta. Sites com login usam o seu: depois do guia, "
        "faça login na aba Fontes."
    ),
    "needs your login": "precisa do seu login",
    "Pick at least one source.": "Escolha pelo menos uma fonte.",
    "Paste your CV or LinkedIn profile, or import a .pdf, .txt or .md file. It's what "
    "the LLM compares each job with. Emails, phone numbers, links and CPF are removed "
    "automatically; remove your name and address yourself. You can also skip this and "
    "do it later, on the Profile tab.": (
        "Cole o seu currículo ou perfil do LinkedIn, ou importe um arquivo .pdf, .txt ou "
        ".md. É com ele que o LLM compara cada vaga. Emails, telefones, links e CPF saem "
        "automaticamente; nome e endereço, tire você mesmo. Também dá para pular e fazer "
        "isso depois, na aba Perfil."
    ),
    "Ollama runs on your computer, for free, but needs installing (ollama.com) and a "
    "good graphics card. Claude, OpenAI and Gemini need an API key and charge per "
    "analysis (cents each). Nothing is spent until you click Analyze on a job.": (
        "O Ollama roda no seu computador, de graça, mas precisa ser instalado "
        "(ollama.com) e de uma boa placa de vídeo. Claude, OpenAI e Gemini pedem uma "
        "chave de API e cobram por análise (centavos cada). Nada é gasto até você clicar "
        "em Analisar numa vaga."
    ),
    "Collect every day at": "Coletar todo dia às",
    "Even with the app closed (Windows Task Scheduler). If the computer is off at that "
    "time, it collects when it's turned on.": (
        "Mesmo com o app fechado (Agendador de Tarefas do Windows). Se o computador "
        "estiver desligado nesse horário, coleta quando for ligado."
    ),
    "Email and WhatsApp can be set up later, on the Settings tab.": (
        "Email e WhatsApp podem ser configurados depois, na aba Configurações."
    ),
    'All set. Click "Collect now" on the Runs tab for the first collection, or wait for '
    "the daily one.": (
        'Tudo pronto. Clique em "Coletar agora" na aba Execuções para a primeira coleta, '
        "ou espere a diária."
    ),
    "Before the first collection, log in to the sources that need it, on the Sources "
    "tab.": (
        "Antes da primeira coleta, faça login nas fontes que pedem, na aba Fontes."
    ),
    "Your CV:": "Seu currículo:",
}
