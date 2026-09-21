(() => {
  "use strict";

  const form = document.getElementById("review-form");
  if (!form || !document.getElementById("scale-readiness-summary")) {
    return;
  }

  const relevantField = (target) => {
    const name = target?.name || "";
    return name.startsWith("scale_") || name.startsWith("ml_score_");
  };

  let timer = null;
  let requestController = null;

  const refresh = async () => {
    const summary = document.getElementById("scale-readiness-summary");
    const url = summary?.dataset.scalePreviewUrl;
    if (!summary || !url) {
      return;
    }

    requestController?.abort();
    requestController = new AbortController();
    summary.setAttribute("aria-busy", "true");
    const feedback = summary.querySelector("[data-scale-preview-feedback]");
    if (feedback) {
      feedback.textContent = "Vorschau wird aktualisiert …";
    }

    try {
      const response = await fetch(url, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {"X-Requested-With": "XMLHttpRequest"},
        signal: requestController.signal,
      });
      if (!response.ok) {
        throw new Error(`Scale preview failed with ${response.status}`);
      }
      summary.outerHTML = await response.text();
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      summary.removeAttribute("aria-busy");
      if (feedback) {
        feedback.textContent = "Vorschau konnte nicht aktualisiert werden. Die serverseitige Prüfung beim Speichern bleibt aktiv.";
      }
    }
  };

  const scheduleRefresh = (event) => {
    if (!relevantField(event.target)) {
      return;
    }
    window.clearTimeout(timer);
    timer = window.setTimeout(refresh, 220);
  };

  form.addEventListener("input", scheduleRefresh);
  form.addEventListener("change", scheduleRefresh);
})();
