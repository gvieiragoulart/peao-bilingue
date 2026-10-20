// Show the latest GitHub Release. The links already lead to Releases if this
// request fails or JavaScript is disabled.
(async () => {
  let release;
  try {
    const response = await fetch(
      "https://api.github.com/repos/gvieiragoulart/peao-bilingue/releases/latest",
      { headers: { Accept: "application/vnd.github+json" } },
    );
    if (!response.ok) return;
    release = await response.json();
  } catch {
    return;
  }
  if (!release || typeof release.tag_name !== "string") return;

  const asset = release.assets?.find((item) =>
    /^PeaoBilingue-Setup-\d+\.\d+\.\d+\.exe$/.test(item.name),
  );
  if (asset?.browser_download_url) {
    for (const link of document.querySelectorAll("[data-download]")) {
      link.href = asset.browser_download_url;
    }
  }
  const values = {
    version: release.tag_name.replace(/^v/, ""),
    size: asset?.size
      ? `${(asset.size / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
      : "",
    sha256: asset?.digest?.startsWith("sha256:") ? asset.digest.slice(7) : "",
  };
  for (const element of document.querySelectorAll("[data-field]")) {
    element.textContent = values[element.dataset.field] ?? "";
  }
  for (const element of document.querySelectorAll("[data-release]")) {
    const needsHash = element.querySelector('[data-field="sha256"]');
    if (!needsHash || values.sha256) element.hidden = false;
  }
})();
