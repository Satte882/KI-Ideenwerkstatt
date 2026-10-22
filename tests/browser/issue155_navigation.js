// Run with playwright-cli run-code on an authenticated outcome/process page.
// No provider endpoints are called; the test only resizes and reads the DOM.
async page => {
  const results = [];
  for (const width of [1440, 1024]) {
    await page.setViewportSize({width, height: 1000});
    const state = await page.evaluate(() => {
      const sidebar = document.querySelector('.app-sidebar');
      const current = [...sidebar.querySelectorAll('[aria-current="page"]')];
      const clipped = [...sidebar.querySelectorAll('.sidebar-link, .sidebar-local-step > span:last-child, .brand strong')]
        .filter(el => el.getClientRects().length && el.scrollWidth > el.clientWidth + 1)
        .map(el => el.textContent.trim());
      return {
        documentOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        sidebarOverflow: sidebar.scrollWidth > sidebar.clientWidth + 1,
        activeMain: [...sidebar.querySelectorAll('.sidebar-link.active')].map(el => el.textContent.trim()),
        current: current.map(el => el.textContent.trim()),
        clipped,
      };
    });
    if (state.documentOverflow || state.sidebarOverflow || state.clipped.length) {
      throw new Error(`Navigation overflow at ${width}: ${JSON.stringify(state)}`);
    }
    if (state.activeMain.length !== 1 || state.current.length !== 1) {
      throw new Error(`Ambiguous navigation at ${width}: ${JSON.stringify(state)}`);
    }
    results.push({width, ...state});
  }
  return results;
}
