(() => {
  const form = document.querySelector("form[data-capture-active-time]");
  const secondsField = form?.querySelector("[data-active-entry-seconds]");
  if (!form || !secondsField) return;

  const maximumSeconds = 900;
  let accumulatedMilliseconds = 0;
  let activeSince = null;

  const isCaptureField = (element) => element?.matches?.("[data-capture-question]");

  const stopClock = () => {
    if (activeSince === null) return;
    accumulatedMilliseconds += performance.now() - activeSince;
    activeSince = null;
  };

  const startClock = () => {
    if (document.visibilityState !== "visible" || activeSince !== null) return;
    activeSince = performance.now();
  };

  form.addEventListener("focusin", (event) => {
    if (isCaptureField(event.target)) startClock();
  });

  form.addEventListener("focusout", (event) => {
    if (isCaptureField(event.target)) stopClock();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && isCaptureField(document.activeElement)) {
      startClock();
    } else {
      stopClock();
    }
  });

  form.addEventListener("submit", () => {
    stopClock();
    const measuredSeconds = Math.floor(accumulatedMilliseconds / 1000);
    secondsField.value = String(Math.min(measuredSeconds, maximumSeconds));
  });
})();
