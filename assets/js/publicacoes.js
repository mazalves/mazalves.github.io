// Página de publicações: filtro por categoria, busca por texto e botão BibTeX.
(() => {
  const page = document.querySelector('.publications-page');
  if (!page) return;
  const buttons = page.querySelectorAll('.publication-filters button');
  const years = page.querySelectorAll('.publication-year');
  const status = page.querySelector('.publication-filter-status');
  const search = page.querySelector('.publication-search');
  let filter = 'all';

  const update = () => {
    const terms = (search ? search.value : '').toLowerCase().split(/\s+/).filter(Boolean);
    let visible = 0;
    years.forEach((section) => {
      let n = 0;
      section.querySelectorAll('.publication-item').forEach((item) => {
        const text = item.dataset.search || '';
        const show = (filter === 'all' || item.dataset.category === filter) &&
                     terms.every((t) => text.includes(t));
        item.hidden = !show;
        if (show) n++;
      });
      section.hidden = n === 0;
      visible += n;
    });
    if (status) status.textContent = `${visible} ${visible === 1 ? 'item' : 'itens'}`;
  };

  buttons.forEach((button) => button.addEventListener('click', () => {
    buttons.forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
    filter = button.dataset.filter;
    update();
  }));
  if (search) search.addEventListener('input', update);

  page.addEventListener('click', async (e) => {
    const btn = e.target.closest('.bibtex-btn');
    if (!btn) return;
    try {
      await navigator.clipboard.writeText(btn.dataset.bibtex);
      const old = btn.textContent; btn.textContent = '✓ copiado / copied';
      setTimeout(() => { btn.textContent = old; }, 1500);
    } catch (_) {
      window.prompt('BibTeX', btn.dataset.bibtex);
    }
  });
  update();
})();
