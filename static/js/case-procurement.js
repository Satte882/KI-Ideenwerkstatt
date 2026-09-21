(() => {
  const scenes = Array.from(document.querySelectorAll("[data-procurement-scene]"));
  if (!scenes.length) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const desktop = window.matchMedia("(min-width: 1051px)");
  let interactive = false;
  let ticking = false;

  const setFinalState = () => {
    scenes.forEach((scene) => {
      const slide = scene.querySelector(".procurement-slide");
      if (!slide) return;
      slide.dataset.step = scene.dataset.steps || "1";
    });
  };

  const updateScenes = () => {
    ticking = false;
    if (!interactive) return;

    scenes.forEach((scene) => {
      const slide = scene.querySelector(".procurement-slide");
      if (!slide) return;

      const steps = Math.max(1, Number.parseInt(scene.dataset.steps || "1", 10));
      const rect = scene.getBoundingClientRect();
      const scrollableDistance = Math.max(1, scene.offsetHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, -rect.top / scrollableDistance));
      const step = Math.min(steps, Math.floor(progress * steps) + 1);

      slide.dataset.step = String(step);
    });
  };

  const requestUpdate = () => {
    if (ticking || !interactive) return;
    ticking = true;
    window.requestAnimationFrame(updateScenes);
  };

  const configure = () => {
    interactive = desktop.matches && !reducedMotion.matches;
    document.documentElement.classList.toggle("procurement-interactive", interactive);

    if (interactive) {
      updateScenes();
    } else {
      setFinalState();
    }
  };

  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("resize", requestUpdate, { passive: true });
  desktop.addEventListener("change", configure);
  reducedMotion.addEventListener("change", configure);

  configure();
})();
