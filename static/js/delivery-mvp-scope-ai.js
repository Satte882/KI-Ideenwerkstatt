(() => {
  'use strict';

  function initMvpScopeAi(root) {
    const form = root.closest('form');
    const target = document.getElementById('id_mvp_scope');
    const inScope = document.getElementById('id_in_scope');
    const outOfScope = document.getElementById('id_out_of_scope');
    const users = document.getElementById('id_users_and_scenarios');
    if (!form || !target || !inScope || !outOfScope || !users) return;

    const csrf = form.querySelector('[name="csrfmiddlewaretoken"]');
    const generateButton = root.querySelector('[data-ai-generate]');
    const generateLabel = root.querySelector('[data-ai-generate-label]');
    const spinner = root.querySelector('[data-ai-spinner]');
    const status = root.querySelector('[data-ai-status]');
    const result = root.querySelector('[data-ai-result]');
    const preview = root.querySelector('[data-ai-preview]');
    const sources = root.querySelector('[data-ai-sources]');
    const missing = root.querySelector('[data-ai-missing]');
    const assumptions = root.querySelector('[data-ai-assumptions]');
    const conflicts = root.querySelector('[data-ai-conflicts]');
    const uncertainty = root.querySelector('[data-ai-uncertainty]');
    const adoptButton = root.querySelector('[data-ai-adopt]');
    const regenerateButton = root.querySelector('[data-ai-regenerate]');
    const discardButton = root.querySelector('[data-ai-discard]');
    const helpfulButton = root.querySelector('[data-ai-helpful]');
    const notHelpfulButton = root.querySelector('[data-ai-not-helpful]');
    const runInput = document.getElementById('id_ai_assist_run_id');
    const editedInput = document.getElementById('id_ai_assist_edited');
    const editRatioInput = document.getElementById('id_ai_assist_edit_ratio');
    const staticReady = root.dataset.staticReady === 'true';

    status.tabIndex = -1;
    helpfulButton.setAttribute('aria-pressed', 'false');
    notHelpfulButton.setAttribute('aria-pressed', 'false');

    let running = false;
    let runId = '';
    let sourceHash = '';
    let adoptedBaseline = null;

    function hasRequiredCurrentContext() {
      return Boolean(inScope.value.trim() && outOfScope.value.trim() && users.value.trim());
    }

    function refreshGenerateAvailability() {
      generateButton.disabled = running || !staticReady || !hasRequiredCurrentContext();
    }

    function setStatus(message, isError = false) {
      status.textContent = message;
      status.classList.toggle('text-danger', isError);
      if (isError) status.focus({preventScroll: true});
    }

    function setRunning(value) {
      running = value;
      generateButton.setAttribute('aria-busy', value ? 'true' : 'false');
      spinner.classList.toggle('d-none', !value);
      generateLabel.textContent = value ? 'KI-Entwurf wird erstellt …' : 'KI-Entwurf erstellen';
      regenerateButton.disabled = value;
      adoptButton.disabled = value;
      discardButton.disabled = value;
      refreshGenerateAvailability();
    }

    function sourceParams() {
      const params = new URLSearchParams();
      params.set('in_scope', inScope.value);
      params.set('out_of_scope', outOfScope.value);
      params.set('users_and_scenarios', users.value);
      params.set('mvp_scope', target.value);
      return params;
    }

    async function post(url, params) {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrf ? csrf.value : '',
        },
        body: params.toString(),
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch (_error) {
        payload = {};
      }
      if (!response.ok || !payload.ok) {
        const error = new Error(payload.message || 'Die Anfrage konnte nicht abgeschlossen werden.');
        error.code = payload.code || 'request_failed';
        error.status = response.status;
        throw error;
      }
      return payload;
    }

    function renderList(element, values, emptyText) {
      element.replaceChildren();
      const items = Array.isArray(values) ? values : [];
      if (!items.length) {
        const item = document.createElement('li');
        item.textContent = emptyText;
        element.appendChild(item);
        return;
      }
      items.forEach((value) => {
        const item = document.createElement('li');
        item.textContent = String(value);
        element.appendChild(item);
      });
    }

    function renderSources(values) {
      sources.replaceChildren();
      const items = Array.isArray(values) ? values : [];
      items.forEach((source) => {
        const item = document.createElement('li');
        const group = source && source.group ? source.group : 'Quelle';
        const label = source && source.label ? source.label : 'Unbenannte Quelle';
        item.textContent = `${group}: ${label}`;
        sources.appendChild(item);
      });
    }

    function renderResult(payload) {
      runId = payload.run_id;
      sourceHash = payload.source_hash;
      preview.value = payload.draft_text || '';
      renderSources(payload.sources);
      renderList(missing, payload.missing_facts, 'Keine offenen Fakten ausgewiesen.');
      renderList(assumptions, payload.assumptions, 'Keine Annahmen ausgewiesen.');
      renderList(conflicts, payload.conflicts, 'Keine Konflikte ausgewiesen.');
      const level = payload.uncertainty && payload.uncertainty.level
        ? payload.uncertainty.level
        : 'unbekannt';
      const reason = payload.uncertainty && payload.uncertainty.reason
        ? payload.uncertainty.reason
        : 'Keine Begründung verfügbar.';
      uncertainty.textContent = `${level}: ${reason}`;
      result.hidden = false;
      result.focus({preventScroll: true});
      preview.focus({preventScroll: true});
      setStatus('KI-Entwurf wurde erstellt. Bitte fachlich prüfen und bei Bedarf bearbeiten.');
    }

    async function generate(regenerated) {
      if (running) return;
      if (!staticReady || !hasRequiredCurrentContext()) {
        setStatus(
          'Vor der Generierung müssen Im Scope, Nicht im Scope und Nutzer/Nutzungsszenarien befüllt sein.',
          true,
        );
        refreshGenerateAvailability();
        return;
      }
      setRunning(true);
      setStatus('OpenRouter erstellt einen feldbezogenen Entwurf. Das kann einige Sekunden dauern.');
      const params = sourceParams();
      if (regenerated) params.set('regenerate', '1');
      try {
        const payload = await post(root.dataset.generateUrl, params);
        renderResult(payload);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setRunning(false);
      }
    }

    async function postEvent(action) {
      const params = sourceParams();
      params.set('action', action);
      params.set('run_id', runId);
      params.set('source_hash', sourceHash);
      return post(root.dataset.eventUrl, params);
    }

    async function adopt() {
      if (!runId || running) return;
      adoptButton.disabled = true;
      try {
        await postEvent('adopt');
      } catch (error) {
        setStatus(error.message, true);
        adoptButton.disabled = false;
        return;
      }
      target.value = preview.value;
      target.dispatchEvent(new Event('input', {bubbles: true}));
      adoptedBaseline = preview.value;
      runInput.value = runId;
      editedInput.value = '0';
      editRatioInput.value = '0';
      setStatus('Entwurf in das Formularfeld übernommen – noch nicht gespeichert.');
      target.focus({preventScroll: true});
      adoptButton.disabled = false;
    }

    function discard() {
      if (runId) postEvent('discard').catch(() => {});
      result.hidden = true;
      preview.value = '';
      runId = '';
      sourceHash = '';
      setStatus('KI-Entwurf verworfen. Der Formularwert wurde nicht verändert.');
      generateButton.focus({preventScroll: true});
    }

    function submitFeedback(action, button) {
      if (!runId) return;
      postEvent(action)
        .then(() => {
          helpfulButton.disabled = true;
          notHelpfulButton.disabled = true;
          button.setAttribute('aria-pressed', 'true');
          setStatus('Feedback wurde erfasst.');
        })
        .catch((error) => setStatus(error.message, true));
    }

    function levenshteinDistance(left, right) {
      if (left === right) return 0;
      if (!left.length) return right.length;
      if (!right.length) return left.length;
      let previous = Array.from({length: right.length + 1}, (_, index) => index);
      for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
        const current = [leftIndex];
        for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
          const cost = left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1;
          current[rightIndex] = Math.min(
            current[rightIndex - 1] + 1,
            previous[rightIndex] + 1,
            previous[rightIndex - 1] + cost,
          );
        }
        previous = current;
      }
      return previous[right.length];
    }

    function captureEditMeasure() {
      if (!runInput.value || adoptedBaseline === null) return;
      const current = target.value;
      const edited = current !== adoptedBaseline;
      const denominator = Math.max(current.length, adoptedBaseline.length, 1);
      const ratio = levenshteinDistance(adoptedBaseline, current) / denominator;
      editedInput.value = edited ? '1' : '0';
      editRatioInput.value = Math.min(1, ratio).toFixed(4);
    }

    generateButton.addEventListener('click', () => generate(false));
    regenerateButton.addEventListener('click', () => generate(true));
    adoptButton.addEventListener('click', adopt);
    discardButton.addEventListener('click', discard);
    helpfulButton.addEventListener('click', () => submitFeedback('helpful', helpfulButton));
    notHelpfulButton.addEventListener('click', () => submitFeedback('not_helpful', notHelpfulButton));
    [inScope, outOfScope, users].forEach((field) => {
      field.addEventListener('input', refreshGenerateAvailability);
    });
    form.addEventListener('submit', captureEditMeasure);
    refreshGenerateAvailability();
  }

  window.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-mvp-scope-ai]').forEach(initMvpScopeAi);
  });
})();
