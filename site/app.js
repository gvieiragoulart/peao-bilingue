// Shows the latest version, its size and its SHA-256 next to the download buttons, from
// /latest.json (written by the release workflow). Without it (offline, nothing released
// yet, JavaScript off) the page still works: the buttons are plain links.
(async () => {
  let latest;
  try {
    const response = await fetch("/latest.json", { cache: "no-cache" });
    if (!response.ok) return;
    latest = await response.json();
  } catch {
    return;
  }
  if (!latest || typeof latest.version !== "string") return;

  const values = {
    version: latest.version,
    size:
      typeof latest.size === "number"
        ? `${(latest.size / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
        : "",
    sha256: typeof latest.sha256 === "string" ? latest.sha256 : "",
  };
  for (const element of document.querySelectorAll("[data-field]")) {
    element.textContent = values[element.dataset.field] ?? "";
  }
  for (const element of document.querySelectorAll("[data-release]")) {
    const needsHash = element.querySelector('[data-field="sha256"]');
    if (!needsHash || values.sha256) element.hidden = false;
  }
})();
