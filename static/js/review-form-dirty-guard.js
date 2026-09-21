(() => {
  "use strict";

  const form = document.getElementById("review-form");
  if (!form) {
    return;
  }

  let isDirty = form.dataset.initiallyDirty === "true";
  let isSubmitting = false;
  const markDirty = () => {
    isDirty = true;
  };

  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);
  form.addEventListener("submit", () => {
    isSubmitting = true;
  });
  window.addEventListener("beforeunload", (event) => {
    if (!isDirty || isSubmitting) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  });
})();
