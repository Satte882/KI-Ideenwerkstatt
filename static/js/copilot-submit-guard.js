document.addEventListener("DOMContentLoaded", () => {
  const attachSubmitGuard = (
    form,
    {buttonLabel, statusLabel = "", waitForPaint = false},
  ) => {
    form.addEventListener("submit", (event) => {
      if (form.dataset.submitted === "true") {
        event.preventDefault();
        return;
      }

      const button =
        event.submitter || form.querySelector('button[type="submit"], button:not([type])');
      if (!button || button.disabled) {
        return;
      }

      const activeButtonLabel = button.dataset.busyLabel || buttonLabel;
      const activeStatusLabel = button.dataset.busyStatus || statusLabel;

      form.dataset.submitted = "true";
      button.disabled = true;
      button.setAttribute("aria-busy", "true");

      if (activeStatusLabel) {
        button.innerHTML =
          '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> ' +
          `<span>${activeButtonLabel}</span>`;
        const status = document.createElement("div");
        status.className = "small text-info mt-2 solution-generation-progress";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.textContent = activeStatusLabel;
        form.insertAdjacentElement("afterend", status);
      } else {
        button.textContent = activeButtonLabel;
      }

      if (waitForPaint) {
        event.preventDefault();
        window.requestAnimationFrame(() => {
          window.requestAnimationFrame(() => {
            HTMLFormElement.prototype.submit.call(form);
          });
        });
      }
    });
  };

  document.querySelectorAll('form[action$="/copilot/"]').forEach((form) => {
    attachSubmitGuard(form, {buttonLabel: "Analyse läuft …"});
  });

  document.querySelectorAll('form[action$="/investigation/start/"], form[data-continue-form]').forEach((form) => {
    attachSubmitGuard(form, {buttonLabel: "Untersuchung wird gestartet …", waitForPaint: true});
  });

  window.addEventListener("pageshow", (event) => {
    if (event.persisted && document.querySelector('form[data-submitted="true"]')) window.location.reload();
  });

  document
    .querySelectorAll('form[action*="/solution-generation/start/"]')
    .forEach((form) => {
      attachSubmitGuard(form, {
        buttonLabel: "KI-Entwürfe werden erstellt …",
        statusLabel: "KI-Generierung läuft. Das kann einige Sekunden dauern.",
        waitForPaint: true,
      });
    });

  document.querySelectorAll("form[data-submit-guard]").forEach((form) => {
    attachSubmitGuard(form, {
      buttonLabel: form.dataset.busyLabel || "Wird verarbeitet …",
      statusLabel: form.dataset.busyStatus || "",
      waitForPaint: true,
    });
  });

  const selectionErrorSummary = document.querySelector("[data-selection-error-summary]");
  if (selectionErrorSummary) {
    selectionErrorSummary.focus({preventScroll: true});
    selectionErrorSummary.scrollIntoView({block: "center"});
  }

  const feedback = document.querySelectorAll(".alert-solution-generation-feedback");
  const solutionArea = document.querySelector("#loesungsoptionen .card-body");
  if (solutionArea && feedback.length) {
    [...feedback].reverse().forEach((message) => {
      message.classList.add("alert-danger", "mb-3");
      const label = document.createElement("strong");
      label.textContent = "KI-Generierung fehlgeschlagen. ";
      message.prepend(label);
      solutionArea.prepend(message);
      message.setAttribute("tabindex", "-1");
    });
    const firstMessage = feedback[0];
    firstMessage.focus({preventScroll: true});
    document.getElementById("loesungsoptionen")?.scrollIntoView({block: "center"});
  }
});
