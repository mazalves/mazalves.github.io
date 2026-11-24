// Página de vídeos: o player só é carregado ao clicar na miniatura; filtro por seção e busca.
(() => {
  const page = document.querySelector('.videos-page');
  if (!page) return;

  page.addEventListener('click', (e) => {
    const thumb = e.target.closest('.video-thumb');
    if (!thumb) return;
    const iframe = document.createElement('iframe');
    iframe.src = thumb.dataset.embed + (thumb.dataset.embed.includes('?') ? '&' : '?') + 'autoplay=1';
    iframe.title = thumb.getAttribute('aria-label') || 'Vídeo';
    iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    thumb.replaceWith(iframe);
  });

  const buttons = page.querySelectorAll('.publication-filters button');
  const sections = page.querySelectorAll('.video-section');
  const search = page.querySelector('.video-search');
  const status = page.querySelector('.video-status');
  let filter = 'all';

  const update = () => {
    const terms = (search.value || '').toLowerCase().split(/\s+/).filter(Boolean);
    let total = 0;
    sections.forEach((sec) => {
      let n = 0;
      sec.querySelectorAll('.video-card').forEach((card) => {
        const show = (filter === 'all' || card.dataset.secao === filter) &&
                     terms.every((t) => (card.dataset.search || '').includes(t));
        card.hidden = !show;
        if (show) n++;
      });
      sec.hidden = n === 0;
      total += n;
    });
    status.textContent = `${total} ${total === 1 ? 'vídeo' : 'vídeos'}`;
  };

  buttons.forEach((b) => b.addEventListener('click', () => {
    buttons.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    filter = b.dataset.filter;
    update();
  }));
  search.addEventListener('input', update);
  update();
})();
