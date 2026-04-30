/**
 * Project Page Main Script (03. コンテンツ一覧)
 * URL: project.html?genre=X&series=Y
 */

let siteStructure = null;
let currentGenre = '';
let currentSeriesKey = '';
let currentSeriesData = null;
let viewMode = 'cards';

const VIEW_MODES = { CARDS: 'cards', SIMPLE_LIST: 'simple-list' };

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) throw new Error('structure.js not loaded');
    siteStructure = window.siteStructure;

    const params = new URLSearchParams(window.location.search);
    currentGenre = decodeURIComponent(params.get('genre') || '');
    currentSeriesKey = decodeURIComponent(params.get('series') || '');

    if (!currentGenre || !currentSeriesKey) {
      showError('シリーズ情報がありません。<a href="index.html">トップへ戻る</a>');
      return;
    }

    currentSeriesData = Series.getEntryByKey(siteStructure, currentGenre, currentSeriesKey);
    if (!currentSeriesData) {
      showError('シリーズが見つかりません。<a href="index.html">トップへ戻る</a>');
      return;
    }

    Series.renderGenreSidebar(document.getElementById('seriesSidebar'), siteStructure, currentGenre);
    updateBreadcrumbs();
    setupViewModeControls();
    renderContentsList();
    setupSearch();
  } catch (error) {
    console.error('Error initializing page:', error);
    showError('ページの読み込みに失敗しました: ' + error.message);
  }
});

function updateBreadcrumbs() {
  const breadcrumb = document.querySelector('.breadcrumbs-content');
  const genreName = Series.getGenreName(siteStructure, currentGenre);
  const seriesName = currentSeriesData.name || currentSeriesKey;
  Navigation.renderBreadcrumbs(breadcrumb, [
    { label: 'トップ', href: 'index.html' },
    { label: genreName, href: Series.buildGenreHref(currentGenre), className: 'breadcrumb-genre' },
    { label: seriesName, current: true, className: 'breadcrumb-current', id: 'seriesName' },
  ]);
}

function renderContentsList() {
  const container = document.getElementById('contentsContainer');
  if (!container) return;
  container.innerHTML = '';
  container.classList.remove('project-grid', 'project-simple-list');
  container.classList.add(viewMode === VIEW_MODES.SIMPLE_LIST ? 'project-simple-list' : 'project-grid');
  hideNoResults();

  const contents = currentSeriesData.contents || [];
  if (contents.length === 0) { showNoResults(); return; }
  for (const content of contents) {
    container.appendChild(
      viewMode === VIEW_MODES.SIMPLE_LIST ? createSimpleContentItem(content) : createContentCard(content)
    );
  }

  if (Array.isArray(currentSeriesData.exturl) && currentSeriesData.exturl.length > 0) {
    const extSection = document.createElement('div');
    extSection.className = 'external-links';
    for (const ext of currentSeriesData.exturl) {
      if (!ext || !ext.url) continue;
      const link = document.createElement('a');
      link.className = 'external-link';
      link.href = ext.url;
      link.textContent = '📄 ' + (ext.caption || ext.url);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      extSection.appendChild(link);
    }
    container.appendChild(extSection);
  }
}

function createContentCard(content) {
  const link = document.createElement('a');
  link.className = 'gallery-item project-content-card';
  link.href = Series.buildGalleryHref(currentGenre, currentSeriesKey, content.path);

  const thumbDiv = document.createElement('div');
  thumbDiv.className = 'gallery-thumbnail project-content-thumb';
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

  const info = document.createElement('div');
  info.className = 'project-content-info';

  const titleDiv = document.createElement('div');
  titleDiv.className = 'project-content-title';
  titleDiv.textContent = content.name || '';

  const mainPersonDiv = document.createElement('div');
  mainPersonDiv.className = 'project-content-line';
  const { classKeys, classNames } = Series.getGenreClassConfig(siteStructure, currentGenre);
  const primaryKey = classKeys[0] || 'main-person';
  const primaryLabel = classNames[0] || '人物';
  const primaryValue = Series.getEntryClassValues(currentSeriesData, primaryKey)[0] || Series.getMainPerson(currentSeriesData);
  mainPersonDiv.textContent = primaryLabel + ': ' + (primaryValue || 'なし');

  const pageCountDiv = document.createElement('div');
  pageCountDiv.className = 'project-content-line';
  pageCountDiv.textContent = 'ページ数: ' + getPageCount(content.path);

  info.appendChild(titleDiv);
  info.appendChild(mainPersonDiv);
  info.appendChild(pageCountDiv);

  link.appendChild(thumbDiv);
  link.appendChild(info);
  return link;
}

function createSimpleContentItem(content) {
  const item = document.createElement('section');
  item.className = 'project-simple-item';
  if (content.cover) {
    const img = document.createElement('img');
    img.src = content.cover;
    img.alt = content.name || '';
    img.className = 'simple-item-thumb';
    img.loading = 'lazy';
    item.appendChild(img);
  }
  const inner = document.createElement('div');
  inner.className = 'simple-item-inner';
  const title = document.createElement('a');
  title.className = 'project-simple-title';
  title.href = Series.buildGalleryHref(currentGenre, currentSeriesKey, content.path);
  title.textContent = content.name || '';
  inner.appendChild(title);
  const meta = document.createElement('span');
  meta.className = 'simple-item-meta';
  meta.textContent = 'ページ数: ' + getPageCount(content.path);
  inner.appendChild(meta);
  item.appendChild(inner);
  return item;
}

function createContentMeta(content) {
  const { pictureCount, videoCount } = getMediaCounts(content.path);
  const meta = document.createElement('div');
  meta.className = 'gallery-meta';
  meta.innerHTML =
    '<span class="gallery-meta-item"><i class="fa-regular fa-images" aria-hidden="true"></i><span>picture:' + pictureCount + '</span></span>' +
    '<span class="gallery-meta-item"><i class="fa-solid fa-film" aria-hidden="true"></i><span>video:' + videoCount + '</span></span>';
  return meta;
}

function collectPages(normalizedPath, map) {
  const resolver = typeof window.resolveGalleryPageEntries === 'function'
    ? window.resolveGalleryPageEntries
    : (value, _fallbackHtml) => (Array.isArray(value) ? value : []);
  if (map[normalizedPath]) return resolver(map[normalizedPath], `contents/${normalizedPath}`);
  const prefix = normalizedPath + '/';
  let all = [];
  for (const [key, pages] of Object.entries(map)) {
    if (key.startsWith(prefix)) all = all.concat(resolver(pages, `contents/${key}`));
  }
  return all;
}

function getMediaCounts(contentPath) {
  const pages = collectPages(normalizePath(contentPath), window.galleryPagesMap || {});
  return pages.reduce((acc, e) => {
    if ((e.type || '') === 'video' || e.video) acc.videoCount += 1;
    else acc.pictureCount += 1;
    return acc;
  }, { pictureCount: 0, videoCount: 0 });
}

function getPageCount(contentPath) {
  return collectPages(normalizePath(contentPath), window.galleryPagesMap || {}).length;
}

function normalizePath(path) {
  return String(path || '').replace(/\\/g, '/').replace(/^\/+/, '');
}

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
  icon.src = iconType === 'cards' ? 'assets/icons/view-mode/ico_card.png' : 'assets/icons/view-mode/ico_list.png';
  button.appendChild(icon);
  button.addEventListener('click', () => {
    if (viewMode === mode) return;
    viewMode = mode;
    updateViewModeControls();
    renderContentsList();
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

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;
  searchInput.placeholder = Search.getSearchPlaceholder(siteStructure, currentGenre, true);

  const navigateToSearch = () => {
    const q = searchInput.value.trim();
    if (!q) return;
    window.location.href = 'index.html?genre=' + encodeURIComponent(currentGenre) + '&q=' + encodeURIComponent(q);
  };

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      navigateToSearch();
    }
    if (e.key === 'Escape') searchInput.value = '';
  });
}

function showNoResults() { document.getElementById('noResults')?.classList.remove('hidden'); }
function hideNoResults() { document.getElementById('noResults')?.classList.add('hidden'); }

function showError(message) {
  const container = document.getElementById('contentsContainer') || document.querySelector('.page-main');
  if (container) container.innerHTML = '<div class="no-results">' + message + '</div>';
}
