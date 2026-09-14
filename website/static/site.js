(() => {
  const menuButton = document.querySelector('#menu-button');
  const mobileMenu = document.querySelector('#mobile-menu');
  if (menuButton && mobileMenu) {
    menuButton.addEventListener('click', () => {
      const opening = mobileMenu.classList.contains('hidden');
      mobileMenu.classList.toggle('hidden');
      menuButton.setAttribute('aria-expanded', String(opening));
    });
  }

  const search = document.querySelector('#live-search');
  const asset = document.querySelector('#asset-filter');
  const assetClass = document.querySelector('#asset-class-filter');
  const evidence = document.querySelector('#evidence-filter');
  const sort = document.querySelector('#sort-filter');
  const grid = document.querySelector('#product-grid');
  const cards = [...document.querySelectorAll('#product-grid .product-card')];
  const count = document.querySelector('#visible-count');
  const empty = document.querySelector('#empty-state');

  const applyLiveFilters = () => {
    if (!cards.length) return;
    const query = (search?.value || '').trim().toLowerCase();
    const assetValue = asset?.value || 'all';
    const assetClassValue = assetClass?.value || 'all';
    const evidenceValue = evidence?.value || 'all';
    let visible = 0;
    cards.forEach((card) => {
      const matchesSearch = !query || card.dataset.search.includes(query);
      const matchesAsset = assetValue === 'all' || card.dataset.symbol === assetValue;
      const matchesAssetClass = assetClassValue === 'all' || card.dataset.asset === assetClassValue;
      const matchesEvidence = evidenceValue === 'all' || card.dataset.evidence.startsWith(evidenceValue);
      const show = matchesSearch && matchesAsset && matchesAssetClass && matchesEvidence;
      card.classList.toggle('hidden', !show);
      if (show) visible += 1;
    });
    if (count) count.textContent = String(visible);
    empty?.classList.toggle('hidden', visible !== 0);

    const number = (card, key, fallback) => {
      const value = Number(card.dataset[key]);
      return Number.isFinite(value) && card.dataset[key] !== '' ? value : fallback;
    };
    const sortValue = sort?.value || 'recommended';
    const comparisons = {
      'recommended': (first, second) => number(first, 'order', 0) - number(second, 'order', 0),
      'pf-desc': (first, second) => number(second, 'pf', -Infinity) - number(first, 'pf', -Infinity),
      'win-desc': (first, second) => number(second, 'win', -Infinity) - number(first, 'win', -Infinity),
      'dd-asc': (first, second) => number(first, 'dd', Infinity) - number(second, 'dd', Infinity),
      'return-desc': (first, second) => number(second, 'return', -Infinity) - number(first, 'return', -Infinity),
      'sharpe-desc': (first, second) => number(second, 'sharpe', -Infinity) - number(first, 'sharpe', -Infinity),
      'recovery-desc': (first, second) => number(second, 'recovery', -Infinity) - number(first, 'recovery', -Infinity),
      'trades-desc': (first, second) => number(second, 'trades', -Infinity) - number(first, 'trades', -Infinity),
      'name-asc': (first, second) => first.dataset.label.localeCompare(second.dataset.label),
    };
    cards.sort(comparisons[sortValue] || comparisons.recommended).forEach((card) => grid?.appendChild(card));
  };

  search?.addEventListener('input', applyLiveFilters);
  asset?.addEventListener('change', applyLiveFilters);
  assetClass?.addEventListener('change', applyLiveFilters);
  evidence?.addEventListener('change', applyLiveFilters);
  sort?.addEventListener('change', applyLiveFilters);
})();
