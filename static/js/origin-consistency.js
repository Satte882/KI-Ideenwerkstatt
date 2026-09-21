(() => {
  const panels = document.querySelectorAll("[data-origin-consistency]");
  panels.forEach((panel) => {
    const generateButton = panel.querySelector("[data-origin-consistency-generate]");
    const regenerateButton = panel.querySelector("[data-origin-consistency-regenerate]");
    const status = panel.querySelector("[data-origin-consistency-status]");
    const resultBox = panel.querySelector("[data-origin-consistency-result]");
    const feedbackBox = panel.querySelector("[data-origin-consistency-feedback]");
    const csrf = panel.querySelector("input[name='csrfmiddlewaretoken']");
    let runId = "";

    const text = (tag, value, className = "") => {
      const node = document.createElement(tag);
      node.textContent = value;
      if (className) node.className = className;
      return node;
    };

    const renderFindings = (findings) => {
      const list = document.createElement("ol");
      list.className = "mb-0";
      findings.forEach((finding) => {
        const item = document.createElement("li");
        item.className = "mb-3";
        item.appendChild(text("strong", finding.finding));
        item.appendChild(
          text(
            "div",
            `Betroffene Felder: ${finding.affected_use_case_fields.join(", ")}`,
            "uc-secondary-copy"
          )
        );
        const refs = finding.source_refs
          .map((source) => `${source.id} @ ${source.version}`)
          .join("; ");
        item.appendChild(text("div", `Quellen: ${refs}`, "uc-secondary-copy"));
        item.appendChild(text("div", `Prüffrage: ${finding.recommended_check}`));
        item.appendChild(
          text(
            "div",
            `Unsicherheit: ${finding.uncertainty.level} – ${finding.uncertainty.reason}`,
            "uc-secondary-copy"
          )
        );
        list.appendChild(item);
      });
      resultBox.appendChild(list);
    };

    const renderResult = (payload) => {
      resultBox.replaceChildren();
      resultBox.classList.remove("d-none");
      if (payload.result === "findings") {
        resultBox.appendChild(text("strong", "Wesentliche Abweichungen gefunden"));
        renderFindings(payload.findings);
      } else if (payload.result === "no_material_drift") {
        resultBox.appendChild(text("strong", "Keine wesentliche Abweichung erkannt."));
      } else {
        resultBox.appendChild(text("strong", "Nicht belastbar prüfbar."));
        const missing = payload.missing_context || [];
        if (missing.length) {
          const list = document.createElement("ul");
          missing.forEach((item) => list.appendChild(text("li", item)));
          resultBox.appendChild(list);
        }
      }
    };

    const runReview = async (regenerate) => {
      generateButton.disabled = true;
      regenerateButton.disabled = true;
      status.textContent = "KI-Herkunftsprüfung läuft …";
      const body = new URLSearchParams();
      if (regenerate) body.set("regenerate", "1");
      try {
        const response = await fetch(panel.dataset.generateUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrf.value,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          },
          body,
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          status.textContent = payload.message || "Die KI-Herkunftsprüfung ist fehlgeschlagen.";
          return;
        }
        runId = payload.run_id;
        renderResult(payload);
        status.textContent = "Prüfung abgeschlossen.";
        regenerateButton.classList.remove("d-none");
        feedbackBox.classList.remove("d-none");
      } catch (_error) {
        status.textContent = "Die KI-Herkunftsprüfung ist derzeit nicht erreichbar.";
      } finally {
        generateButton.disabled = false;
        regenerateButton.disabled = false;
      }
    };

    const sendFeedback = async (helpful) => {
      if (!runId) return;
      const body = new URLSearchParams({
        run_id: runId,
        action: helpful ? "helpful" : "not_helpful",
      });
      try {
        const response = await fetch(panel.dataset.feedbackUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrf.value,
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          },
          body,
        });
        if (response.ok) {
          feedbackBox.replaceChildren(text("span", "Feedback erfasst.", "uc-secondary-copy"));
        }
      } catch (_error) {
        status.textContent = "Feedback konnte nicht erfasst werden.";
      }
    };

    generateButton?.addEventListener("click", () => runReview(false));
    regenerateButton?.addEventListener("click", () => runReview(true));
    panel.querySelector("[data-origin-consistency-helpful='1']")?.addEventListener(
      "click",
      () => sendFeedback(true)
    );
    panel.querySelector("[data-origin-consistency-helpful='0']")?.addEventListener(
      "click",
      () => sendFeedback(false)
    );
  });
})();
