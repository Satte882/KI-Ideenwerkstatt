document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-file-staging]").forEach((stagingArea) => {
    const input = stagingArea.querySelector("[data-file-staging-input]");
    const addButton = stagingArea.querySelector("[data-file-staging-add]");
    const summary = stagingArea.querySelector("[data-file-staging-summary]");
    const list = stagingArea.querySelector("[data-file-staging-list]");
    if (!input || !addButton || !summary || !list) return;

    let stagedFiles = [];
    const fileKey = (file) => `${file.name}:${file.size}:${file.lastModified}`;

    const render = () => {
      list.replaceChildren();
      stagedFiles.forEach((file, index) => {
        const item = document.createElement("li");
        item.className = "d-flex align-items-center justify-content-between gap-2 py-1";

        const filename = document.createElement("span");
        filename.textContent = file.name;
        item.append(filename);

        const remove = document.createElement("button");
        remove.className = "btn btn-sm btn-link text-danger p-0";
        remove.type = "button";
        remove.dataset.fileStagingRemove = String(index);
        remove.setAttribute("aria-label", `${file.name} entfernen`);
        remove.textContent = "Entfernen";
        item.append(remove);
        list.append(item);
      });

      summary.textContent = stagedFiles.length
        ? `${stagedFiles.length} Datei(en) für den Quellenstand ausgewählt.`
        : "Noch keine Dateien ausgewählt.";
    };

    const syncInput = () => {
      if (typeof DataTransfer === "undefined") {
        stagedFiles = Array.from(input.files || []);
        render();
        return;
      }
      const transfer = new DataTransfer();
      stagedFiles.forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
      render();
    };

    input.addEventListener("change", () => {
      const known = new Set(stagedFiles.map(fileKey));
      Array.from(input.files || []).forEach((file) => {
        const key = fileKey(file);
        if (!known.has(key)) {
          stagedFiles.push(file);
          known.add(key);
        }
      });
      syncInput();
    });

    addButton.addEventListener("click", () => input.click());
    list.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-file-staging-remove]");
      if (!remove) return;
      stagedFiles.splice(Number(remove.dataset.fileStagingRemove), 1);
      syncInput();
    });
  });
});
