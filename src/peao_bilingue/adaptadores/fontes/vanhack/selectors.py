"""Seletores do site da VanHack, todos documentados.

Mapeado contra o site real em 2026-10-05.

O login é **passwordless** e fica em `auth.vanhack.com`, fora do app
(`app.vanhack.com/login` responde 404). Os seletores de login existem apenas
para **detectar** a tela de login e o desafio do Cloudflare — nunca para
preencher o formulário, que é sempre tarefa manual do usuário.
"""

# --- Tela de login (auth.vanhack.com) -------------------------------------

# Texto do subtítulo; confirma que o fluxo não usa senha.
LOGIN_SUBTITLE = "No password needed"

# Campo de email do formulário de magic link.
LOGIN_EMAIL_INPUT = 'input[type="email"]'

# Botões de login social; o formulário de email usa o submit "Continue".
LOGIN_LINKEDIN_BUTTON = "Continue with LinkedIn"
LOGIN_GOOGLE_BUTTON = "Continue with Google"
LOGIN_SUBMIT_BUTTON = "Continue"

# Honeypot: input de texto rotulado "Website", invisível para humanos.
# Preencher este campo marca a sessão como bot. NUNCA interagir com ele.
LOGIN_HONEYPOT_LABEL = "Website"

# --- Desafio humano (Cloudflare Turnstile) --------------------------------

# O widget roda dentro de um iframe do Cloudflare.
TURNSTILE_IFRAME = 'iframe[src*="challenges.cloudflare.com"]'

# Mensagem exibida quando o Turnstile recusa o navegador (caso típico de
# navegador automatizado): "Security check could not complete. Refresh this
# page or try another browser."
SECURITY_CHECK_FAILED = "Security check could not complete"

# Outros indicadores genéricos de bloqueio/verificação.
CHALLENGE_TEXTS = (
    SECURITY_CHECK_FAILED,
    "Verify you are human",
    "Confirme que é humano",
    "Checking your browser",
)

# --- Página de perfil (/profile) ------------------------------------------
# Mapeada contra o site real. O layout é semântico e estável: `pf-*` é o
# perfil, `vh-*` é o design system. Os ids gerados pelo Blazor
# (`0HNP0Q2EPN2A7`, `vhdd-<guid>-button`) mudam a cada render — nunca usar.

PROFILE_READY = "#profile-first-name"  # âncora: perfil renderizado

SECTION = "section.pf-section"
SECTION_TITLE = "h5.pf-section-title"

# Par pergunta/resposta: label.pf-label + um controle (dropdown ou autocomplete).
FIELD = "div.pf-field"
FIELD_LABEL = "label.pf-label"
DROPDOWN = "div.vh-dd"  # dropdown custom; o texto é o valor escolhido
AUTOCOMPLETE_INPUT = "input.form-control"  # valor fica em input_value()

# Um campo pode ter radios, checkboxes ou várias linhas (ex.: 7 países).
RADIO_MARCADO = "label.pf-radio:has(input:checked)"
CHECKBOX_MARCADO = "label.pf-check:has(input:checked)"
TARGET_ROW = "div.pf-target-row"  # uma preferência de país por linha

# Texto que esses controles exibem quando nada foi escolhido.
VALORES_VAZIOS = ("Select an option", "Choose a country", "Select Language")

# Skills: dois grupos (top 3 e secundárias), identificados pelo título.
SKILL_GROUP = "div.pf-skill-group"
SKILL_GROUP_TITLE = "div.pf-skill-group-title"
SKILL_ROW = "div.pf-skill-row"
SKILL_SELECT = "div.pf-skill-select"
SKILL_YEARS = "div.pf-skill-years"
GRUPO_SKILLS_PRINCIPAIS = "Rank your top 3 skills"
GRUPO_SKILLS_SECUNDARIAS = "Add 5 secondary skills"

# Idiomas
LANG_ROW = "div.pf-lang-row"
LANG_SELECT = "div.pf-lang-select"
LANG_LEVEL = "div.pf-lang-level"

# Experiência: uma empresa pode ter vários cargos.
EXPERIENCE = "div.pf-exp"
EXP_COMPANY = "a.pf-item-title"
EXP_INDUSTRY = "div.pf-item-sub"
EXP_ROLE = "div.pf-role"
EXP_ROLE_HEAD = "div.pf-role-head"  # cargo + período, no mesmo texto
EXP_ROLE_DESC = "div.pf-role-desc"
EXP_ROLE_CHIPS = "div.pf-chips span.vh-chip"  # uma skill por chip; há chips com espaço

# Formação
EDUCATION_DEGREE = "div.pf-degree"

# Nível de inglês avaliado no Intro Video, no formato "Level: Fluent".
INTRO_VIDEO_CARD = "div.pf-intro-video-card"
INTRO_VIDEO_NIVEL = r"Level:\s*(\w+)"

# Links sociais, identificados pelo placeholder.
LINK_INPUTS = {
    "linkedin": 'input[placeholder="http://linkedin.com/"]',
    "github": 'input[placeholder="http://github.com/"]',
    "site": 'input[placeholder="http://sitename.com/"]',
}

# Rótulos das perguntas que viram campos estruturados do snapshot.
LABEL_CARGO = "Which role best applies to your experience?"
LABEL_ANOS_TI = "For how many years have you been working as an IT professional?"
LABEL_LIDERANCA = "Do you have leadership experience?"
LABEL_ANOS_LIDERANCA = "Years of leadership"
LABEL_REMOTO = "Are you open to remote jobs?"
LABEL_DISPONIBILIDADE = "When would you be available to start a new job?"

# PII: nunca entra no snapshot nem no prompt (ver "Regras inegociáveis").
# Além destes, a URL do currículo é assinada (token SAS) e também fica de fora.
PII_LABELS = (
    "phone",
    "passport",
    "visa",
    "email",
    "birth",
    "document",
    "citizenship",
    "name",
)

# --- Listagem de vagas (/jobs e /jobs/{slug}-jobs) ------------------------
# A busca é feita por URL: /jobs/python-jobs filtra de verdade (conferido
# comparando os ids devolvidos). A listagem tem **scroll infinito**: 10 cards
# no primeiro render, 25 depois de rolar.

CARDS_CONTAINER = "div.vh-cards"
# Busca sem resultado: o container existe e mostra "You're seeing 0 jobs".
EMPTY_STATE_TEXT = "You're seeing 0 jobs"
# Escopar os links ao container é obrigatório: a página da vaga tem
# `a.vh-jd-minicard` apontando para outras vagas (recomendadas/recentes).
CARD_LINK = "a.vh-card-link"
CARD = "div.vh-card"
CARD_EYEBROW = "div.vh-eyebrow"  # ex.: "BACKEND ENGINEER · 8+ YEARS OF EXPERIENCE"
CARD_TITLE = "h2.vh-card-title"
CARD_LOCATION = "span.vh-detail-label"
CARD_MODE = "span.vh-mode-pill"  # "Hybrid" / "Fully remote"
CARD_SKILL = "span.vh-skill"
CARD_SKILL_MUST = "vh-skill-must"  # modificador: skill obrigatória
CARD_POSTED = "span.vh-posted"
CARD_SALARY = "div.vh-salary-amount"
CARD_CANDIDATE_LOCATION = "div.vh-card-candidate-location"

JOB_URL_ID = r"/job/(\d+)"  # o id da vaga vem da URL, nunca do texto

# --- Página da vaga (/job/{id}) -------------------------------------------

JD_ROOT = "div.vh-jd"
JD_TITLE = "section.vh-jd-hero h1"
JD_FACT = "span.vh-jd-fact"
JD_MODE = "span.vh-jd-mode-pill"
JD_CANDIDATE_LOCATION = "div.vh-jd-candidate-location"
JD_DESCRIPTION = "div.vh-jd-description"
JD_SALARY = "span.vh-jd-apply-salary-amount"

# Blocos de skill: cabeçalho (MUST-HAVE / NICE-TO-HAVE / LANGUAGES) + chips.
JD_SUBBLOCK = "div.vh-jd-subblock"
JD_SUBBLOCK_HEAD = "div.vh-jd-skill-key-head"
JD_CHIP = "span.vh-jd-skill"
JD_CHIP_YEARS = "small"  # dentro do chip: "5 Year(s)"
JD_HEAD_MUST = "MUST-HAVE"
JD_HEAD_NICE = "NICE-TO-HAVE"
JD_HEAD_LANGUAGES = "LANGUAGES"

# A VanHack **não publica a empresa**: nem no card, nem na página da vaga
# (a descrição diz "our hiring partner"). `empresa` fica None de propósito.
