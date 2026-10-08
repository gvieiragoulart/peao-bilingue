from pathlib import Path

from filelock import FileLock, Timeout

from peao_bilingue.dominio.coleta import Trava


class TravaDeArquivo(Trava):
    """Lock de arquivo: exclui a interface e a tarefa agendada, que são processos diferentes.

    Cria uma instância nova de FileLock a cada tentativa: a mesma instância é
    reentrante e deixaria passar uma segunda execução do mesmo processo.
    Instâncias diferentes se excluem, no mesmo processo e entre processos.
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self._ativa: FileLock | None = None

    def adquirir(self) -> bool:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        trava = FileLock(self.caminho)
        try:
            trava.acquire(timeout=0)
        except Timeout:
            return False
        self._ativa = trava
        return True

    def liberar(self) -> None:
        if self._ativa is not None:
            self._ativa.release()
            self._ativa = None
