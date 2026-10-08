class SessaoExpirada(RuntimeError):
    """A fonte exige login e a sessão salva não vale mais. O login é sempre manual."""


class LoginFalhou(RuntimeError):
    """O login manual não terminou (tempo esgotado ou sessão não confirmada)."""


class DesafioHumano(RuntimeError):
    """Captcha ou verificação humana na página. O sistema nunca tenta resolver."""


class ErroDeColeta(RuntimeError):
    """Falha ao ler uma fonte; `artefato` aponta para o screenshot + HTML salvos."""

    def __init__(self, mensagem: str, artefato: str | None = None) -> None:
        super().__init__(mensagem)
        self.artefato = artefato


class ExecucaoEmAndamento(RuntimeError):
    """Já existe uma execução rodando; só uma por vez."""


class ErroDeAgendamento(RuntimeError):
    """O sistema operacional recusou criar, ler ou remover a tarefa agendada."""


class ProvedorIndisponivel(RuntimeError):
    """O provedor de LLM está fora do ar ou mal configurado; a mensagem diz o que fazer."""


class AnaliseInvalida(RuntimeError):
    """O provedor de LLM não produziu uma análise válida dentro das tentativas."""


class PerfilAusente(LookupError):
    """Nenhum perfil lido da fonte pedida, e a análise precisa de um."""


class NomeDesconhecido(LookupError):
    """Nenhum adapter registrado com esse nome."""
