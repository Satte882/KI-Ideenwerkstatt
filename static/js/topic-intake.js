document.querySelectorAll('[data-topic-intake]').forEach((form) => {
  const text = form.querySelector('[name="text"]');
  const title = form.querySelector('[name="title"]');
  let edited = Boolean(title.value);
  title.addEventListener('input', () => { edited = true; });
  text.addEventListener('input', () => {
    if (!edited) {
      const compact = text.value.trim().replace(/\s+/g, ' ');
      const head = compact.slice(0, 79);
      title.value = compact.length <= 80 ? compact : (head.replace(/\s+\S*$/, '') || head) + '…';
    }
  });
});
