document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("solution-generation-adoption-form");
  if (!form) return;

  const checkboxes = Array.from(
    document.querySelectorAll('input[name="selected_lanes"][form="solution-generation-adoption-form"]'),
  );
  const submitButton = form.querySelector('[data-testid="adopt-selected-solutions"]');

  const render = () => {
    const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
    if (submitButton) {
      submitButton.disabled = selectedCount === 0;
      submitButton.textContent = `${selectedCount} ausgewählte KI-Lösungsoption${selectedCount === 1 ? "" : "en"} hinzufügen`;
    }

    checkboxes.forEach((checkbox) => {
      const card = checkbox.closest("[data-generated-option]");
      if (!card) return;
      const discardButton = card.querySelector("[data-discard-generated-option]");
      const status = card.querySelector("[data-generated-option-status]");
      card.classList.toggle("opacity-50", !checkbox.checked);
      if (discardButton) {
        discardButton.textContent = checkbox.checked ? "Vorschlag verwerfen" : "Wieder aufnehmen";
        discardButton.setAttribute("aria-pressed", checkbox.checked ? "false" : "true");
      }
      if (status) {
        status.textContent = checkbox.checked
          ? "Für die Übernahme ausgewählt"
          : "Wird nicht übernommen";
      }
    });
  };

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", render);
    const card = checkbox.closest("[data-generated-option]");
    const discardButton = card?.querySelector("[data-discard-generated-option]");
    discardButton?.addEventListener("click", () => {
      checkbox.checked = !checkbox.checked;
      checkbox.dispatchEvent(new Event("change", {bubbles: true}));
    });
  });

  render();
});
