document.addEventListener("DOMContentLoaded", () => {
  const rows = document.querySelectorAll("[data-row-link]");

  rows.forEach((row) => {
    const openRow = () => {
      window.location.assign(row.dataset.rowLink);
    };

    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea")) {
        return;
      }
      openRow();
    });

    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      openRow();
    });
  });
});
