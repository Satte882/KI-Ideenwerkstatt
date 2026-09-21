(() => {
  "use strict";

  const labels = ["sehr gering", "gering", "mittel", "hoch", "sehr hoch"];

  function displayValue(input) {
    const value = Number(input.value);
    const label = labels[value] || "";
    return label ? `${value} · ${label}` : String(value);
  }

  function update(input, markTouched) {
    const outputId = input.dataset.output;
    const touchedId = input.dataset.touched;
    const output = outputId ? document.getElementById(outputId) : null;
    const touched = touchedId ? document.getElementById(touchedId) : null;

    if (markTouched && touched) touched.value = "1";
    if (!output) return;

    const assessed = !touched || touched.value === "1";
    output.textContent = assessed ? displayValue(input) : "Nicht bewertet";
    output.dataset.assessed = assessed ? "true" : "false";
  }

  document.querySelectorAll(".work-design-range").forEach((input) => {
    input.disabled = false;
    input.dataset.ratingReady = "true";
    update(input, false);
    ["pointerdown", "keydown", "input", "change"].forEach((eventName) => {
      input.addEventListener(eventName, () => update(input, true));
    });
  });
})();
