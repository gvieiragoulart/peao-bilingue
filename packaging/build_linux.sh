#!/usr/bin/env bash
# Build a portable x86_64 Linux bundle and its checksum.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "The Linux release is built for x86_64." >&2
  exit 1
fi

version="$(uv version --short)"
archive="PeaoBilingue-linux-x86_64-${version}.tar.gz"

uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm

staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cp -a dist/PeaoBilingue "$staging/PeaoBilingue"
install -m 0644 LICENSE.md "$staging/PeaoBilingue/LICENSE.md"
install -m 0644 packaging/linux-release-readme.txt "$staging/PeaoBilingue/README.txt"
uv run --no-sync --group packaging python packaging/third_party_notices.py \
  "$staging/PeaoBilingue/THIRD_PARTY_NOTICES.txt"

tar -C "$staging" -czf "dist/$archive" PeaoBilingue
(cd dist && sha256sum "$archive" > "$archive.sha256")
echo "Built dist/$archive"
