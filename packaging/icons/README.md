# App icon candidates

The eight icons drawn on the design canvas
(https://claude.ai/artifact/NTsQVNMHGSAMHg5wCyCJ1n), on 2026-10-18, in the blue
`#3A86F7`. Each SVG has a 256 px PNG preview next to it.

| File | Name on the canvas | |
|---|---|---|
| `p-bubble.svg` | 7 · P no balão | **the app's icon** |
| `p-rounded.svg` | 5 · P arredondado | |
| `p-geometric.svg` | 6 · P geométrico | |
| `p-signal.svg` | 8 · P com sinal | |
| `pawn-antenna.svg` | 1 · Peão-antena | |
| `pawn-bilingual.svg` | 2 · Peão bilíngue | |
| `two-bubbles.svg` | 3 · Dois balões | |
| `radar.svg` | 4 · Radar | |

`packaging/app_icon.py` renders them and writes the chosen one to
`src/peao_bilingue/ui/peao_bilingue.ico`, the icon of `PeaoBilingue.exe` and of the
window:

```bash
uv run --with pillow python packaging/app_icon.py            # p-bubble
uv run --with pillow python packaging/app_icon.py radar      # another one
```
