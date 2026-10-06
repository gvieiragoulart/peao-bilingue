# VanHack Watcher

Serviço pessoal que, todo dia às 08:00 (America/Sao_Paulo), entra na VanHack pelo navegador,
coleta as vagas por scraping, filtra por buscas configuráveis, analisa cada vaga nova com o Claude
e avisa por email (análise completa) e WhatsApp (resumo).

Para cada vaga nova a análise traz fit score, resumo do encaixe, passos de preparação,
exatamente 20 perguntas de entrevista, gaps e o que melhorar no perfil.

O perfil do candidato não é mantido à mão: a cada execução o sistema lê
`https://app.vanhack.com/profile`, guarda um snapshot e usa sempre a versão mais recente.

---

## Instalação

```bash
uv sync
uv run playwright install chromium
cp .env.example .env     # preencha as credenciais
```

### O login é manual, sempre

A VanHack usa login **sem senha** (link por email, Google ou LinkedIn) atrás do Cloudflare
Turnstile. Não existe login automático: você loga uma vez e a sessão fica salva.

```bash
uv run vanhack-login
```

Abre uma janela do Chrome. Se escolher entrar por email, **copie o link recebido e cole na barra
dessa janela** — clicar no link pelo cliente de email cria a sessão no navegador errado. A
verificação "confirme que é humano" é sua; o robô nunca a resolve.

Confira depois que a sessão está valendo:

```bash
uv run vanhack-check
```

---

## Uso

```bash
uv run vanhack-run --dry-run                              # coleta e analisa, sem notificar
uv run vanhack-run                                        # coleta, analisa e notifica
uv run uvicorn vanhack_watcher.main:app --port 8000       # painel + agendador
```

Com a API no ar, `http://127.0.0.1:8000/docs` abre a documentação interativa.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | último run, se há sessão salva, próxima execução agendada |
| GET POST | `/searches` | listar e criar buscas |
| PUT DELETE | `/searches/{id}` | atualizar e remover |
| GET | `/jobs` | filtros: `status`, `min_score`, `search`, paginação |
| GET PATCH | `/jobs/{id}` | detalhe com a análise vigente; mudar status |
| POST | `/jobs/{id}/reanalyze` | nova análise (ex.: depois de editar `profile_notes.md`) |
| GET | `/profile` | snapshot mais recente |
| GET | `/profile/history` | snapshots e os campos que mudaram entre eles |
| POST | `/profile/sync` | sincroniza só o perfil |
| GET POST | `/runs` | histórico e disparo manual (409 se já estiver rodando) |

Cadastre ao menos uma busca antes da primeira coleta:

```bash
curl -X POST http://127.0.0.1:8000/searches -H "Content-Type: application/json" \
  -d '{"name":"Python remoto","keywords":["python","django"],"exclude":["junior"]}'
```

**Rode sempre com 1 worker:** o agendador vive dentro do processo.

---

## Rodar como serviço

O agendador é interno (APScheduler com `coalesce` e tolerância de 6 h), então basta manter o
processo da API no ar: se a máquina estava desligada às 08:00, a coleta acontece uma vez quando
o app sobe.

### Windows — Agendador de Tarefas

Mantém a API rodando a cada logon:

```bash
schtasks /create /tn "VanHack Watcher" /sc onlogon /rl highest ^
  /tr "cmd /c cd /d C:\Users\vieir\vanhack-watcher && uv run uvicorn vanhack_watcher.main:app --port 8000"
```

Se preferir **não** manter a API no ar, agende só a coleta:

```bash
schtasks /create /tn "VanHack Watcher - coleta" /sc daily /st 08:00 ^
  /tr "cmd /c cd /d C:\Users\vieir\vanhack-watcher && uv run vanhack-run"
```

Marque "Executar estando o usuário conectado ou não" só se o `uv` estiver no PATH do sistema;
caso contrário use o caminho completo (`C:\Users\<voce>\.local\bin\uv.exe`).

### Windows — NSSM (serviço de verdade)

```bash
nssm install VanHackWatcher "C:\Users\vieir\.local\bin\uv.exe" "run uvicorn vanhack_watcher.main:app --port 8000"
nssm set VanHackWatcher AppDirectory "C:\Users\vieir\vanhack-watcher"
nssm start VanHackWatcher
```

### Linux — systemd

`/etc/systemd/system/vanhack-watcher.service`:

```ini
[Unit]
Description=VanHack Watcher
After=network-online.target

[Service]
Type=simple
User=gabriel
WorkingDirectory=/opt/vanhack-watcher
ExecStart=/usr/local/bin/uv run uvicorn vanhack_watcher.main:app --port 8000
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now vanhack-watcher
```

### Docker (VPS)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --frozen
ENV BROWSER_CHANNEL=""
CMD ["uv", "run", "uvicorn", "vanhack_watcher.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`BROWSER_CHANNEL=""` é obrigatório no container.** Por padrão o projeto usa o Chrome instalado
na máquina (o Cloudflare recusa navegadores atípicos), e dentro da imagem só existe o Chromium
do Playwright.

Monte `data/` como volume para a sessão e o banco sobreviverem ao redeploy:

```bash
docker run -d --env-file .env -v $PWD/data:/app/data -p 8000:8000 vanhack-watcher
```

---

## Sessão expirada no VPS

O login exige interação humana (Turnstile e, no caso do magic link, o email), então **não dá para
logar dentro do servidor**. Quando `/health` mostrar o último run com status `login_required`:

1. Na sua máquina, rode `uv run vanhack-login` e faça o login.
2. Copie o `data/state.json` gerado para o servidor:
   ```bash
   scp data/state.json usuario@servidor:/opt/vanhack-watcher/data/state.json
   ```
3. Reinicie o serviço (`sudo systemctl restart vanhack-watcher` ou `docker restart ...`).

O `state.json` contém cookies de sessão: trate como senha, nunca versione (já está no
`.gitignore`) e copie por canal seguro.

---

## Desenvolvimento

```bash
uv run pytest                         # testes, todos offline
uv run ruff check . && uv run ruff format .
```

Os testes usam HTML real anonimizado em `tests/fixtures/` (veja o README de lá) e nunca abrem
conexão com a VanHack, com SMTP, com a Twilio nem com a API do Claude.

Convenções e decisões do projeto estão em [CLAUDE.md](CLAUDE.md).
