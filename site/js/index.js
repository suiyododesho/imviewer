/**
 * Index Page Main Script (02. シリーズ一覧)
 * Handles series listing by genre, view mode, search.
 */

let siteStructure = null;
let siteConfig = null;
let activeGenre = '';
let viewMode = 'cards';
let classBrowseMode = false;
let classBrowseValue = '';

const VIEW_MODES = { CARDS: 'cards', SIMPLE_LIST: 'simple-list' };

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }
    siteStructure = window.siteStructure;
    siteConfig = window.siteConfig || {};

    const params = new URLSearchParams(window.location.search);
    activeGenre = getRequestedGenre(params.get('genre'));
    classBrowseMode = params.get('classBrowse') === '1';
    classBrowseValue = decodeURIComponent(params.get('classValue') || '').trim();

    Series.renderGenreSidebar(document.getElementById('seriesSidebar'), siteStructure, activeGenre);
    setupViewModeControls();
    updateBreadcrumbs();
    renderSeriesList();
    setupSearch();
    handlePersonParam(params);
  } catch (error) {
    console.error('Error initializing page:', error);
    showError('サイトの読み込みに失敗しました: ' + error.message);
  }
});

// ============ Genre filtering ============

function getRequestedGenre(requested) {
  const genres = Series.getGenres(siteStructure);
  const keys = Object.keys(genres);
  if (keys.length === 0) return '';
  if (requested && genres[requested]) return requested;
  const configured = siteConfig && siteConfig.defaultSeries;
  if (configured && genres[configured]) return configured;
  return keys[0];
}

function getActiveEntries() {
  if (activeGenre) {
    const entries = Series.getSeriesEntries(siteStructure, activeGenre);
    return Object.entries(entries).map(([seriesKey, data]) => ({ genreKey: activeGenre, seriesKey, data }));
  }
  return Series.getAllSeriesEntries(siteStructure);
}

// ============ Rendering ============

function updateBreadcrumbs() {
  const breadcrumb = document.getElementById('breadcrumbTrail');
  const items = [{ label: 'トップ', href: 'index.html' }];
  const genreName = Series.getGenreName(siteStructure, activeGenre);
  const { classNames } = Series.getGenreClassConfig(siteStructure, activeGenre);

  if (activeGenre) {
    if (classBrowseMode) {
      items.push({ label: genreName, href: Series.buildGenreHref(activeGenre) });
      items.push({
        label: '全' + (classNames[0] || '分類') + '一覧',
        href: Series.buildGenreClassBrowseHref(activeGenre),
      });
      if (classBrowseValue) {
        items.push({ label: classBrowseValue, current: true });
      } else {
        items[items.length - 1].current = true;
      }
    } else {
      items.push({ label: genreName, current: true });
    }
  } else {
    items[0].current = true;
  }

  Navigation.renderBreadcrumbs(breadcrumb, items);
}

function renderSeriesList() {
  const container = document.getElementById('projectsContainer');
  if (!container) return;

  container.innerHTML = '';
  container.classList.remove('project-grid', 'project-simple-list');
  hideNoResults();

  const entries = getActiveEntries();
  if (entries.length === 0) { showNoResults(); return; }

  if (classBrowseMode) {
    renderClassBrowseList(container, entries);
    return;
  }

  container.classList.add(viewMode === VIEW_MODES.SIMPLE_LIST ? 'project-simple-list' : 'project-grid');

  for (const { genreKey, seriesKey, data } of entries) {
    container.appendChild(
      viewMode === VIEW_MODES.SIMPLE_LIST
        ? createSimpleSeriesItem(genreKey, seriesKey, data)
        : createSeriesCard(genreKey, seriesKey, data)
    );
  }
}

function renderClassBrowseList(container, entries) {
  const { classKeys, classNames, browse } = Series.getGenreClassConfig(siteStructure, activeGenre);
  if (classKeys.length === 0) {
    container.classList.add(viewMode === VIEW_MODES.SIMPLE_LIST ? 'project-simple-list' : 'project-grid');
    for (const { genreKey, seriesKey, data } of entries) {
      container.appendChild(
        viewMode === VIEW_MODES.SIMPLE_LIST
          ? createSimpleSeriesItem(genreKey, seriesKey, data)
          : createSeriesCard(genreKey, seriesKey, data)
      );
    }
    return;
  }

  const primaryKey = classKeys[0];
  const primaryName = classNames[0] || primaryKey;

  if (!classBrowseValue) {
    const values = collectClassValueCounts(entries, primaryKey);
    if (values.length === 0) {
      showNoResults();
      return;
    }

    const section = document.createElement('div');
    section.className = 'search-series-section';

    const heading = document.createElement('h2');
    heading.className = 'search-series-heading';
    heading.textContent = primaryName + '一覧';
    section.appendChild(heading);

    const chips = document.createElement('div');
    chips.className = 'persons-chips';
    for (const item of values) {
      const link = document.createElement('a');
      link.className = 'person-chip';
      link.href = Series.buildGenreClassBrowseHref(activeGenre, item.value);
      link.textContent = item.value + ' (' + item.count + ')';
      chips.appendChild(link);
    }

    section.appendChild(chips);
    container.appendChild(section);
    return;
  }

  const filtered = entries.filter(({ data }) =>
    Series.getEntryClassValues(data, primaryKey).includes(classBrowseValue)
  );

  if (filtered.length === 0) {
    showNoResults();
    return;
  }

  const heading = document.createElement('h2');
  heading.className = 'search-series-heading';
  heading.textContent = primaryName + ': ' + classBrowseValue;
  container.appendChild(heading);

  if (classKeys.length < 2) {
    if (browse.leafType === 'content') {
      appendContentLeafSection(container, filtered, browse);
    } else {
      appendSeriesLeafGrid(container, filtered);
    }
    return;
  }

  const secondaryKey = classKeys[1];
  const secondaryName = classNames[1] || secondaryKey;
  const groups = groupEntriesByClassValue(filtered, secondaryKey, browse.unknownLabel || '未分類');

  for (const [groupName, groupEntries] of groups) {
    const section = document.createElement('div');
    section.className = 'search-series-section';

    const sectionHeading = document.createElement('h3');
    sectionHeading.className = 'search-series-heading';
    sectionHeading.textContent = secondaryName + ': ' + groupName;
    section.appendChild(sectionHeading);

    const grid = document.createElement('div');
    if (browse.leafType === 'content') {
      appendContentLeafSection(section, groupEntries, browse);
    } else {
      grid.className = 'project-grid';
      for (const { genreKey, seriesKey, data } of groupEntries) {
        grid.appendChild(createSeriesCard(genreKey, seriesKey, data));
      }
      section.appendChild(grid);
    }
    container.appendChild(section);
  }
}

function appendSeriesLeafGrid(container, entries) {
  const grid = document.createElement('div');
  grid.className = 'project-grid';
  for (const { genreKey, seriesKey, data } of entries) {
    grid.appendChild(createSeriesCard(genreKey, seriesKey, data));
  }
  container.appendChild(grid);
}

function appendContentLeafSection(container, entries, browse) {
  const allItems = [];
  for (const { genreKey, seriesKey, data } of entries) {
    const contents = Array.isArray(data.contents) ? data.contents : [];
    for (const content of contents) {
      allItems.push({ genreKey, seriesKey, content });
    }
  }

  if (allItems.length === 0) {
    return;
  }

  const groups = groupContentLeafItems(allItems, browse);

  for (const [groupName, items] of groups) {
    if (groups.size > 1) {
      const contentHeading = document.createElement('h4');
      contentHeading.className = 'search-series-heading';
      contentHeading.textContent = groupName;
      container.appendChild(contentHeading);
    }

    const grid = document.createElement('div');
    grid.className = 'gallery-grid';
    for (const item of items) {
      grid.appendChild(createContentItem(item.content, item.genreKey, item.seriesKey));
    }
    container.appendChild(grid);
  }
}

function collectClassValueCounts(entries, classKey) {
  const counts = new Map();
  for (const { data } of entries) {
    const values = Series.getEntryClassValues(data, classKey);
    for (const value of values) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
  }

  return Array.from(counts.entries())
    .sort((a, b) => a[0].localeCompare(b[0], 'ja'))
    .map(([value, count]) => ({ value, count }));
}

function groupEntriesByClassValue(entries, classKey, unknownLabel = '未分類') {
  const groups = new Map();
  for (const entry of entries) {
    const values = Series.getEntryClassValues(entry.data, classKey);
    const primary = values[0] || unknownLabel;
    if (!groups.has(primary)) {
      groups.set(primary, []);
    }
    groups.get(primary).push(entry);
  }

  return new Map(
    Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0], 'ja'))
  );
}

function groupContentLeafItems(items, browse) {
  const mode = (browse && browse.contentGroupBy) || 'flat';
  if (mode === 'flat' || mode === 'none') {
    return new Map([['', items]]);
  }

  const depth = mode === 'path-depth-2' ? 2 : 1;
  const unknownLabel = (browse && browse.unknownLabel) || '未分類';
  const groups = new Map();

  for (const item of items) {
    const path = (item && item.content && typeof item.content.path === 'string') ? item.content.path : '';
    const parts = path.split('/').filter(Boolean);
    const key = parts.length >= depth ? parts[depth - 1] : unknownLabel;
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(item);
  }

  return new Map(Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0], 'ja')));
}

function createSeriesCard(genreKey, seriesKey, data) {
  const link = document.createElement('a');
  link.className = 'series-card-item';
  link.href = Series.buildSeriesHref(genreKey, seriesKey);

  const thumbDiv = document.createElement('div');
  thumbDiv.className = 'series-card-thumb';
  const cover = Series.getFirstContentCover(data);
  if (cover) {
    const img = document.createElement('img');
    img.src = cover;
    img.alt = data.name || seriesKey;
    img.loading = 'lazy';
    img.onerror = () => { img.style.display = 'none'; thumbDiv.innerHTML = '<div class="series-card-placeholder">No image</div>'; };
    thumbDiv.appendChild(img);
  } else {
    thumbDiv.innerHTML = '<div class="series-card-placeholder">No image</div>';
  }

  const info = document.createElement('div');
  info.className = 'series-card-info';

  const titleDiv = document.createElement('div');
  titleDiv.className = 'series-card-title';
  titleDiv.textContent = data.name || seriesKey;

  const mainPersonDiv = document.createElement('div');
  mainPersonDiv.className = 'series-card-line';
  const { classKeys, classNames } = Series.getGenreClassConfig(siteStructure, genreKey);
  const primaryKey = classKeys[0] || 'main-person';
  const primaryLabel = classNames[0] || '人物';
  const primaryValue = Series.getEntryClassValues(data, primaryKey)[0] || Series.getMainPerson(data);
  mainPersonDiv.textContent = primaryLabel + ': ' + (primaryValue || 'なし');

  const countDiv = document.createElement('div');
  countDiv.className = 'series-card-line';
  countDiv.textContent = 'コンテンツ: ' + Series.getContentCount(data) + '件';

  info.appendChild(titleDiv);
  info.appendChild(mainPersonDiv);
  info.appendChild(countDiv);

  link.appendChild(thumbDiv);
  link.appendChild(info);
  return link;
}

function createSimpleSeriesItem(genreKey, seriesKey, data) {
  const item = document.createElement('section');
  item.className = 'project-simple-item';

  const cover = Series.getFirstContentCover(data);
  if (cover) {
    const img = document.createElement('img');
    img.src = cover;
    img.alt = data.name || seriesKey;
    img.className = 'simple-item-thumb';
    img.loading = 'lazy';
    item.appendChild(img);
  }

  const inner = document.createElement('div');
  inner.className = 'simple-item-inner';

  const title = document.createElement('a');
  title.className = 'project-simple-title';
  title.textContent = data.name || seriesKey;
  title.href = Series.buildSeriesHref(genreKey, seriesKey);
  inner.appendChild(title);

  const { classKeys, classNames } = Series.getGenreClassConfig(siteStructure, genreKey);
  const primaryKey = classKeys[0] || 'main-person';
  const primaryLabel = classNames[0] || '人物';
  const primaryValue = Series.getEntryClassValues(data, primaryKey)[0] || Series.getMainPerson(data);
  const count = Series.getContentCount(data);
  const meta = document.createElement('span');
  meta.className = 'simple-item-meta';
  meta.textContent = [primaryLabel + ': ' + (primaryValue || 'なし'), 'コンテンツ ' + count + '件'].filter(Boolean).join(' / ');
  inner.appendChild(meta);

  item.appendChild(inner);
  return item;
}

function makePlaceholder(text) {
  const el = document.createElement('div');
  el.className = 'project-banner-placeholder';
  el.textContent = text;
  return el;
}

// ============ Navigation ============

function navigateToSeries(genreKey, seriesKey) {
  window.location.href = Series.buildSeriesHref(genreKey, seriesKey);
}

// ============ View Mode ============

function setupViewModeControls() {
  const controls = document.getElementById('viewModeControls');
  if (!controls) return;
  controls.innerHTML = '';
  controls.appendChild(createViewModeButton(VIEW_MODES.CARDS, 'cards', 'カード表示'));
  controls.appendChild(createViewModeButton(VIEW_MODES.SIMPLE_LIST, 'simple-list', 'シンプルリスト表示'));
  updateViewModeControls();
}

function createViewModeButton(mode, iconType, label) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'view-mode-button';
  button.dataset.mode = mode;
  button.title = label;
  button.setAttribute('aria-label', label);
  button.setAttribute('aria-pressed', 'false');

  const icon = document.createElement('img');
  icon.className = 'view-mode-icon-image';
  icon.alt = '';
  icon.setAttribute('aria-hidden', 'true');
  icon.src = iconType === 'cards'
    ? 'assets/icons/view-mode/ico_card.png'
    : 'assets/icons/view-mode/ico_list.png';
  button.appendChild(icon);

  button.addEventListener('click', () => {
    if (viewMode === mode) return;
    viewMode = mode;
    updateViewModeControls();
    const searchInput = document.getElementById('searchInput');
    if (searchInput && searchInput.value.trim().length > 0) return;
    renderSeriesList();
  });
  return button;
}

function updateViewModeControls() {
  const controls = document.getElementById('viewModeControls');
  if (!controls) return;
  controls.querySelectorAll('.view-mode-button').forEach((btn) => {
    const active = btn.dataset.mode === viewMode;
    btn.classList.toggle('is-active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (query.length === 0) {
      showSeriesView();
      renderSeriesList();
    } else {
      showSearchView();
      renderSearchResults(Search.searchEntriesGroupedByGenre(siteStructure, query));
    }
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const query = searchInput.value.trim();
      if (query.length > 0) {
        showSearchView();
        renderSearchResults(Search.searchEntriesGroupedByGenre(siteStructure, query));
      }
    }
    if (e.key === 'Escape') {
      searchInput.value = '';
      showSeriesView();
      renderSeriesList();
    }
  });
}

function handlePersonParam(params) {
  const person = params.get('person');
  if (!person) return;
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = person;
  showSearchView();
  renderSearchResults(Search.searchEntriesGroupedByGenre(siteStructure, person, true));
}

function showSeriesView() {
  document.getElementById('projectsContainer')?.classList.remove('hidden');
  document.getElementById('searchResults')?.classList.add('hidden');
  document.getElementById('noResults')?.classList.add('hidden');
}

function showSearchView() {
  document.getElementById('projectsContainer')?.classList.add('hidden');
  document.getElementById('searchResults')?.classList.remove('hidden');
}

function renderSearchResults(genreGroups) {
  const container = document.getElementById('searchResultsContent');
  if (!container) return;
  container.innerHTML = '';

  if (genreGroups.length === 0) { showNoResults(); return; }
  hideNoResults();

  for (const { genreName, genreKey, entries } of genreGroups) {
    const section = document.createElement('div');
    section.className = 'search-series-section';

    const heading = document.createElement('h2');
    heading.className = 'search-series-heading';
    heading.textContent = genreName;
    section.appendChild(heading);

    for (const { seriesKey, data, matchedPerson } of entries) {
      const block = document.createElement('div');
      block.className = 'search-project-block';

      const labelEl = document.createElement('div');
      labelEl.className = 'search-project-label';
      const link = document.createElement('a');
      link.href = Series.buildSeriesHref(genreKey, seriesKey);
      link.textContent = data.name || seriesKey;
      labelEl.appendChild(link);
      if (matchedPerson) {
        const span = document.createElement('span');
        span.textContent = ' - ' + matchedPerson;
        labelEl.appendChild(span);
      }
      block.appendChild(labelEl);

      if (Array.isArray(data.exturl) && data.exturl.length > 0) {
        block.appendChild(createExternalLinksBlock(data.exturl));
      }

      const grid = document.createElement('div');
      grid.className = 'gallery-grid';
      for (const content of (data.contents || [])) {
        grid.appendChild(createContentItem(content, genreKey, seriesKey));
      }
      block.appendChild(grid);
      section.appendChild(block);
    }
    container.appendChild(section);
  }
}

function createContentItem(content, genreKey, seriesKey) {
  const link = document.createElement('a');
  link.className = 'gallery-item';
  link.href = Series.buildGalleryHref(genreKey, seriesKey, content.path);

  const thumbDiv = document.createElement('div');
  thumbDiv.className = 'gallery-thumbnail';
  if (content.cover) {
    const img = document.createElement('img');
    img.src = content.cover;
    img.alt = content.name || '';
    img.loading = 'lazy';
    img.onerror = () => { img.style.display = 'none'; thumbDiv.innerHTML = '<div class="gallery-thumbnail-placeholder">No image</div>'; };
    thumbDiv.appendChild(img);
  } else {
    thumbDiv.innerHTML = '<div class="gallery-thumbnail-placeholder">No image</div>';
  }
  link.appendChild(thumbDiv);

  const labelDiv = document.createElement('div');
  labelDiv.className = 'gallery-label';
  labelDiv.textContent = content.name || '';
  link.appendChild(labelDiv);
  return link;
}

function createExternalLinksBlock(extUrls) {
  const block = document.createElement('div');
  block.className = 'external-links';
  for (const ext of extUrls) {
    if (!ext || !ext.url) continue;
    const link = document.createElement('a');
    link.className = 'external-link';
    link.href = ext.url;
    link.textContent = '📄 ' + (ext.caption || ext.url);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    block.appendChild(link);
  }
  return block;
}

// ============ Utilities ============

function showNoResults() {
  document.getElementById('noResults')?.classList.remove('hidden');
}

function hideNoResults() {
  document.getElementById('noResults')?.classList.add('hidden');
}

function showError(message) {
  const main = document.querySelector('.page-main');
  if (main) main.innerHTML = '<div class="no-results">' + message + '</div>';
}
