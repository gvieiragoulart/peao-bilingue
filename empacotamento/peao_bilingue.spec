# Spec do PyInstaller do Peão Bilíngue: uma pasta, app de janela (sem console).
#
#   uv run --group empacotar pyinstaller empacotamento/peao_bilingue.spec --noconfirm
#
# Sai em dist/PeaoBilingue/PeaoBilingue.exe. Sem argumentos abre a janela; com
# argumentos é a CLI (é assim que a tarefa agendada roda a coleta).
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

RAIZ = Path(SPECPATH).parent  # noqa: F821 - SPECPATH vem do PyInstaller

datas = [
    # O driver do Playwright (node + pacote JS). O Chromium NÃO entra: o app usa o
    # Chrome instalado (BROWSER_CHANNEL=chrome), o mesmo que o Cloudflare aceita.
    *collect_data_files("playwright"),
    # O keyring acha o backend do Cofre do Windows por entry points.
    *copy_metadata("keyring"),
]

hiddenimports = [
    # Os adapters são importados pelo registro (importlib), não por import direto.
    *collect_submodules("peao_bilingue"),
    *collect_submodules("keyring.backends"),
    "win32ctypes.core",
    # O SQLAlchemy carrega o dialeto pelo nome da URL ("sqlite://").
    "sqlalchemy.dialects.sqlite",
]

a = Analysis(
    [str(RAIZ / "src" / "peao_bilingue" / "inicio.py")],
    pathex=[str(RAIZ / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "_pytest", "IPython", "mypy", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PeaoBilingue",
    console=False,  # app de janela; a coleta agendada escreve em coleta.log
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PeaoBilingue", upx=False)
