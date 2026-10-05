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

  if (!groups.length || !status || !evidence || !decision) {
    return;
  }

  const fundingCommands = new Set(["start_pilot", "go_live"]);

  const syncFundingVisibility = () => {
    const relevant = fundingCommands.has(decision.value);
    groups.forEach((group) => {
      group.classList.toggle("d-none", !relevant);
      group.setAttribute("aria-hidden", relevant ? "false" : "true");
    });
    status.disabled = !relevant;
    evidence.disabled = !relevant;
  };

  decision.addEventListener("change", syncFundingVisibility);
  syncFundingVisibility();
})();
