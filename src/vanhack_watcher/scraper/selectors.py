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

# --- Listagem, detalhe e perfil -------------------------------------------
# Ainda não mapeados: dependem de uma sessão logada (Fase 4).
# Observações do reconhecimento inicial, a confirmar com HTML real:
#   - app Blazor (LeptonX), classes com prefixo `vh-*`
#   - busca por URL: /jobs/{slug}-jobs (~10 resultados, sem paginação)
#   - página da vaga: /job/{id}
#   - cards da listagem não mostram a empresa
