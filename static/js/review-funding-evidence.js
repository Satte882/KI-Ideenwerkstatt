(() => {
  "use strict";

  const form = document.getElementById("review-form");
  if (!form) {
    return;
  }

  const groups = [...form.querySelectorAll("[data-funding-evidence-group]")];
  const status = form.querySelector('[name="funding_status"]');
  const evidence = form.querySelector('[name="funding_evidence"]');
  const decision = form.querySelector('[name="decision"]');
  const targetStatus = form.querySelector('[name="new_status"]');
  const feedback = form.querySelector('[data-funding-feedback]');
  const closureGroups = [...form.querySelectorAll("[data-review-closure-group]")];

  if (!decision) {
    return;
  }

  const fundingCommands = new Set(["start_pilot", "go_live"]);

  const syncFundingVisibility = () => {
    closureGroups.forEach((group) => {
      const ending = decision.value === "end";
      group.classList.toggle("d-none", !ending);
      group.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !ending;
      });
    });
    if (!status || !evidence) {
      return;
    }
    const relevant = fundingCommands.has(decision.value);
    groups.forEach((group) => {
      group.classList.toggle("d-none", !relevant);
      group.setAttribute("aria-hidden", relevant ? "false" : "true");
    });
    status.disabled = !relevant;
    evidence.disabled = !relevant;
    evidence.required = relevant && ["satisfied", "not_required"].includes(status.value);
    if (feedback) {
      feedback.textContent = status.value === "open"
        ? "Finanzierung ist offen. Klärung bleibt erforderlich; die Entscheidung ist weiterhin möglich."
        : status.value === ""
          ? "Finanzierung ist noch unbekannt. Dies bleibt im Entscheidungsnachweis sichtbar."
          : "";
    }
  };

  const syncDecision = () => {
    if (targetStatus && !targetStatus.disabled) {
      const targets = {start_review: "review", start_pilot: "pilot", go_live: "operation", end: "ended"};
      targetStatus.value = targets[decision.value] || form.dataset.currentStatus;
    }
    syncFundingVisibility();
  };
  decision.addEventListener("change", syncDecision);
  status?.addEventListener("change", syncFundingVisibility);
  syncFundingVisibility();
})();
