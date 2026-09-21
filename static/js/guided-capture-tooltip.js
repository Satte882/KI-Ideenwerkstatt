document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((trigger) => {
    bootstrap.Tooltip.getOrCreateInstance(trigger);
  });
});
