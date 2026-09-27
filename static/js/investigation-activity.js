(() => {
  const root = document.getElementById("investigation-activity");
  if (!root) return;
  const timeline = root.querySelector("[data-timeline]");
  const connection = root.querySelector("[data-connection]");
  const announcement = root.querySelector("[data-announcement]");
  const newActivities = root.querySelector("[data-new-activities]");
  let state = JSON.parse(document.getElementById("investigation-activity-initial").textContent);
  let receivedAt = performance.now();
  let delay = 2000;
  let timer;
  let controller;
  let offline = false;
  const isActive = (value) => ["running", "waiting_human"].includes(value);
  let stopped = !isActive(state.status);
  const text = (selector, value) => { root.querySelector(selector).textContent = value || ""; };
  const duration = (seconds) => {
    const total = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor(total / 60) % 60;
    const sec = total % 60;
    return (hours ? `${String(hours).padStart(2, "0")}:` : "") +
      `${String(minutes).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };
  const clock = () => {
    if (offline || document.hidden) return;
    const now = Date.parse(state.server_time) + performance.now() - receivedAt;
    if (isActive(state.status)) {
      text("[data-total-duration]", duration((now - Date.parse(state.started_at)) / 1000));
    }
    if (state.execution_lease_until && now >= Date.parse(state.execution_lease_until)) {
      root.classList.add("activity-offline");
      text("[data-activity-description]", "Ausführung derzeit nicht bestätigt. Der letzte gespeicherte Stand bleibt sichtbar.");
      return;
    }
    state.entries.forEach((entry) => {
      if (entry.status !== "running" || !entry.started_at) return;
      const node = [...timeline.children].find((item) => item.dataset.entryId === entry.id);
      if (node) node.querySelector("[data-entry-duration]").textContent =
        duration((now - Date.parse(entry.started_at)) / 1000);
    });
  };
  const createEntry = () => {
    const node = document.createElement("li");
    node.innerHTML = '<span class="activity-node" aria-hidden="true" data-node></span>' +
      '<div class="activity-entry-content"><div class="activity-entry-heading">' +
      '<strong data-label></strong><span class="activity-duration" data-entry-duration></span></div>' +
      '<p class="activity-entry-detail" data-detail></p><details class="activity-technical">' +
      '<summary>Technische Schrittdetails</summary><div data-technical></div>' +
      '<a data-audit-link hidden>Quelle oder reproduzierbare Analyse öffnen</a></details></div>';
    return node;
  };
  const render = (next) => {
    const added = [];
    const nearBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 120;
    const existing = new Map([...timeline.children].map((node) => [node.dataset.entryId, node]));
    const changed = [];
    next.entries.forEach((entry, index) => {
      let node = existing.get(entry.id);
      if (!node) { node = createEntry(); added.push(node); }
      if (node.dataset.entryStatus !== entry.status) changed.push(entry.label);
      node.className = `activity-entry activity-entry--${entry.status}`;
      node.dataset.entryId = entry.id;
      node.dataset.entryStatus = entry.status;
      node.dataset.startedAt = entry.started_at || "";
      node.querySelector("[data-node]").textContent =
        ({success: "✓", failed: "×", review: "!", running: "●"})[entry.status] || "–";
      node.querySelector("[data-label]").textContent = entry.label;
      node.querySelector("[data-entry-duration]").textContent = entry.duration;
      node.querySelector("[data-detail]").textContent = entry.detail;
      node.querySelector("[data-technical]").textContent = entry.technical;
      node.querySelector("details").hidden = !entry.technical;
      const audit = node.querySelector("[data-audit-link]");
      audit.hidden = !entry.audit_url;
      if (entry.audit_url) audit.href = entry.audit_url;
      if (timeline.children[index] !== node) timeline.insertBefore(node, timeline.children[index] || null);
      existing.delete(entry.id);
    });
    existing.forEach((node) => node.remove());
    added.forEach((node) => node.classList.add("activity-new"));
    if (added.length && !nearBottom) newActivities.hidden = false;
    text("[data-activity-title]", next.title);
    const headingStatus = root.querySelector("[data-heading-status]");
    headingStatus.className = `activity-heading-status activity-heading-status--${next.execution_state}`;
    headingStatus.textContent = next.ready ? "✓" : next.status === "failed" ? "×" : next.status === "waiting_human" ? "!" : "●";
    root.querySelector("[data-result-jump]").hidden = !next.ready;
    text("[data-activity-description]", next.description);
    text("[data-total-duration]", next.duration);
    text("[data-duration-label]", next.finished_at ? "Gesamtdauer seit Start" : "Seit Start");
    const attention = next.status === "waiting_human" || next.status === "failed";
    root.querySelector("[data-attention]").hidden = !attention;
    text("[data-attention-title]", next.status === "waiting_human" ? "Entscheidungskritische Klärung" : "Technische Prüfung erforderlich");
    text("[data-impact]", next.impact);
    text("[data-required-action]", next.required_action);
    text("[data-needed-evidence]", next.needed_evidence ? `Benötigt: ${next.needed_evidence}` : "");
    text("[data-clarification-question]", next.clarification_question || "Antwort auf die offene Klärung");
    root.querySelector("[data-continue-form]").hidden = !next.can_continue;
    root.querySelector("[data-abort-form]").hidden = !next.can_abort;
    const result = root.querySelector("[data-result]");
    if (next.ready && result.hidden) result.classList.add("activity-new");
    result.hidden = !next.ready;
    if (next.brief_url) root.querySelector("[data-brief-link]").href = next.brief_url;
    if (next.title !== state.title || changed.length) {
      announcement.textContent = next.title !== state.title ? next.title : changed[changed.length - 1];
    }
    state = next;
    receivedAt = performance.now();
    stopped = !isActive(next.status);
    clock();
  };
  const schedule = () => {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(poll, delay);
  };
  const poll = async () => {
    if (controller || stopped || document.hidden) return;
    controller = new AbortController();
    const timeout = setTimeout(() => controller?.abort(), 10000);
    try {
      const response = await fetch(root.dataset.statusUrl, {
        credentials: "same-origin", cache: "no-store", signal: controller.signal,
        headers: {Accept: "application/json"},
      });
      if (response.status === 403 || response.status === 404 || response.redirected) {
        stopped = true;
        throw new Error("access");
      }
      if (!response.ok) throw new Error("network");
      const next = await response.json();
      offline = false;
      connection.hidden = true;
      root.classList.remove("activity-offline");
      delay = next.status === "waiting_human" ? 5000 : 2000;
      render(next);
    } catch (error) {
      offline = true;
      root.classList.add("activity-offline");
      connection.hidden = false;
      connection.textContent = error.message === "access" ?
        "Der Zugriff ist nicht mehr bestätigt. Bitte Seite neu öffnen oder erneut anmelden." :
        "Live-Aktualisierung unterbrochen. Der letzte bestätigte Stand bleibt sichtbar. Die Verbindung wird erneut geprüft.";
      delay = Math.min(delay * 2, 15000);
    } finally {
      clearTimeout(timeout);
      controller = null;
      schedule();
    }
  };
  newActivities.addEventListener("click", () => {
    timeline.lastElementChild?.scrollIntoView({block: "center"});
    newActivities.hidden = true;
  });
  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (document.hidden) root.classList.add("activity-offline");
    else if (!stopped) poll();
  });
  window.addEventListener("pagehide", () => { clearTimeout(timer); controller?.abort(); });
  setInterval(clock, 1000);
  schedule();
})();
