(() => {
  const stepTargets = {
    value_stream: {
      id: "value-stream",
      selector: ".architecture-summary-grid",
    },
    focus: {
      id: "fokus-priorisierung",
      selector: ".architecture-summary-grid + .decision-panel",
    },
    process: {
      id: "prozessanalyse",
      selector: "#prozessdetails + .app-card",
    },
    solution: {
      id: "loesungsoptionen",
      selector: "#loesungsoptionen",
    },
  };

  function elevateMethodologyLabels() {
    const marker = " Methodik: ";

    document.querySelectorAll(".card-header .small.text-muted").forEach((description) => {
      const text = description.textContent.trim();
      const markerIndex = text.indexOf(marker);
      if (markerIndex === -1) return;

      const heading = description.parentElement?.querySelector(":scope > strong");
      if (!heading || heading.nextElementSibling?.dataset.methodologyLabel === "true") return;

      const summary = text.slice(0, markerIndex);
      const methodology = text.slice(markerIndex + marker.length).replace(/\.$/, "");
      description.textContent = summary;

      const label = document.createElement("span");
      label.className = "small text-muted fw-normal ms-1";
      label.dataset.methodologyLabel = "true";
      label.textContent = `(${methodology})`;
      heading.insertAdjacentElement("afterend", label);
    });
  }

  function prepareTargets() {
    Object.values(stepTargets).forEach(({ id, selector }) => {
      const target = document.querySelector(selector);
      if (!target) return;
      if (!document.getElementById(id)) target.id = id;
    });
  }

  function focusRequestedStep() {
    const requestedStep = new URLSearchParams(window.location.search).get("analysis_step");
    const definition = stepTargets[requestedStep];
    if (!definition) return;

    const target = document.getElementById(definition.id);
    if (!target) return;

    if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "start" });
  }

  function updateDisclosureLabel(details, closedLabel, openLabel) {
    const summary = details.querySelector(":scope > summary");
    if (!summary) return;
    summary.textContent = details.open ? openLabel : closedLabel;
  }

  function enhanceFocusCriteria() {
    document.querySelectorAll(".kpi-strip").forEach((strip) => {
      if (strip.children.length !== 5) return;
      strip.style.removeProperty("grid-template-columns");
      strip.classList.add("kpi-strip-responsive");
    });
  }

  function enhanceValueStreamStages() {
    document.querySelectorAll(".value-stream-stage").forEach((stage) => {
      if (stage.dataset.layoutEnhanced === "true") return;

      // Newer templates already render stage facts with the shared native
      // disclosure. Keep process/use-case links and real actions outside that
      // disclosure instead of wrapping them in a second generated one.
      if (stage.querySelector(":scope > details[data-testid='stage-details']")) {
        stage.dataset.layoutEnhanced = "true";
        return;
      }

      const detailSections = Array.from(
        stage.querySelectorAll(":scope > .stage-facts, :scope > .stage-use-cases"),
      );
      if (!detailSections.length) return;

      const details = document.createElement("details");
      details.className = "architecture-disclosure stage-disclosure";

      const summary = document.createElement("summary");
      details.append(summary);

      detailSections[0].insertAdjacentElement("beforebegin", details);
      detailSections.forEach((section) => details.append(section));

      const closedLabel = "Phasendetails anzeigen";
      const openLabel = "Phasendetails ausblenden";
      details.addEventListener("toggle", () => {
        updateDisclosureLabel(details, closedLabel, openLabel);
      });
      updateDisclosureLabel(details, closedLabel, openLabel);
      stage.dataset.layoutEnhanced = "true";
    });
  }

  function enhanceProcessArtifacts() {
    document.querySelectorAll(".architecture-artifact-grid > section").forEach((section) => {
      if (section.dataset.layoutEnhanced === "true") return;

      const title = section.querySelector(":scope > .section-title");
      const contentLength = section.textContent.trim().length;
      if (!title || contentLength < 180) return;

      const details = document.createElement("details");
      details.className = "architecture-disclosure artifact-disclosure";

      const summary = document.createElement("summary");
      summary.textContent = title.textContent.trim();
      details.append(summary);

      title.remove();
      while (section.firstChild) details.append(section.firstChild);
      section.append(details);
      section.dataset.layoutEnhanced = "true";
    });
  }

  function enhanceLongSourceLists() {
    const processPage = document.querySelector(".architecture-artifact-grid");
    if (!processPage) return;

    document.querySelectorAll(".alert > ul").forEach((list) => {
      if (list.dataset.layoutEnhanced === "true") return;
      if (list.children.length < 3 && list.textContent.trim().length < 240) return;

      const details = document.createElement("details");
      details.className = "architecture-disclosure source-disclosure mt-2";

      const summary = document.createElement("summary");
      details.append(summary);
      list.insertAdjacentElement("beforebegin", details);
      details.append(list);

      const closedLabel = "Quellendetails anzeigen";
      const openLabel = "Quellendetails ausblenden";
      details.addEventListener("toggle", () => {
        updateDisclosureLabel(details, closedLabel, openLabel);
      });
      updateDisclosureLabel(details, closedLabel, openLabel);
      list.dataset.layoutEnhanced = "true";
    });
  }

  function enhanceArchitectureLayout() {
    enhanceFocusCriteria();
    enhanceValueStreamStages();
    enhanceProcessArtifacts();
    enhanceLongSourceLists();
  }

  document.addEventListener("DOMContentLoaded", () => {
    elevateMethodologyLabels();
    prepareTargets();
    enhanceArchitectureLayout();
    focusRequestedStep();
  });
})();
