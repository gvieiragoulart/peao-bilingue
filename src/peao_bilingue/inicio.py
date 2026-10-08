"""Ponto de entrada do .exe: sem argumentos abre a janela; com argumentos é a CLI.

Um executável só serve aos dois: o atalho abre o app, e a tarefa agendada chama
`PeaoBilingue.exe run --agendado` sem janela nenhuma (o .exe é de interface, sem
console; com `--agendado` o registro vai para `coleta.log`).
"""

import sys


def main() -> None:
    # Imports aqui dentro: a coleta agendada não precisa carregar o Tk.
    if len(sys.argv) > 1:
        from peao_bilingue.cli import main as cli

        cli()
    else:
        from peao_bilingue.ui.app import main as abrir_janela

        abrir_janela()


if __name__ == "__main__":
    main()
