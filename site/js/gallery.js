/**
 * Gallery Page Main Script
 * Renders image and video media directly with dedicated navigation.
 */

let siteStructure = null;
let currentGenre = null;
let currentSeriesKey = null;
let currentContentPath = null;
let currentSeriesData = null;
let currentGallery = null;
let currentGalleries = [];
let currentGalleryIndex = -1;
let galleryPages = [];
let currentPageIndex = 0;
let thumbnailGenerationToken = 0;

const ZOOM_LEVELS = [100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 1000, 1200, 1400, 1600];
const ZOOM_MIN_PERCENT = ZOOM_LEVELS[0];
const ZOOM_MAX_PERCENT = ZOOM_LEVELS[ZOOM_LEVELS.length - 1];

const zoomState = {
  percent: ZOOM_MIN_PERCENT,
  panX: 0,
  panY: 0,
  isDragging: false,
  pointerId: null,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginPanX: 0,
  dragOriginPanY: 0,
  activeImage: null,
  spreadWrapper: null,
  stage: null,
  control: null,
  slider: null,
  valueLabel: null,
  touchPoints: new Map(),
  isPinching: false,
  pinchStartDistance: 0,
  pinchStartPercent: ZOOM_MIN_PERCENT,
  controlFadeTimer: null,
  lastCenterTapTimeMs: 0,
  lastCenterTapX: 0,
  lastCenterTapY: 0,
};

const thumbnailModeState = {
  enabled: false,
  panel: null,
  toggle: null,
  busyOverlay: null,
  transitionToken: 0,
  activeThumbButton: null,
  hasOpenedOnce: false,
  suppressAutoScrollOnce: false,
};

const thumbnailCacheState = {
  entries: new Map(),
  objectUrls: new Set(),
};

const thumbnailUiState = {
  pendingPanelIndexes: new Set(),
  panelRefreshScheduled: false,
};

const thumbnailVirtualState = {
  content: null,
  rafScheduled: false,
  columns: 1,
  cellSize: 76,
  gap: 10,
  startIndex: -1,
  endIndex: -1,
};

const thumbnailWarmupState = {
  running: false,
  sessionId: 0,
  cursor: 0,
  inflight: 0,
  maxInflight: 2,
  loadedSources: new Set(),
};

const swipeNavState = {
  tracking: false,
  pointerId: null,
  startX: 0,
  startY: 0,
  lastX: 0,
  lastY: 0,
  startTimeMs: 0,
  axis: 'none',
};

const STAGE_THUMBNAIL_SIZE = 176;
const GALLERY_VIEW_MODE_STORAGE_KEY_PREFIX = 'imviewer.gallery.viewMode';
const GALLERY_VIEW_MODE_LEGACY_STORAGE_KEY = 'imviewer.gallery.viewMode';
const GALLERY_VIEW_MODE_SCOPE_SMARTPHONE = 'sp';
const GALLERY_VIEW_MODE_SCOPE_DEFAULT = 'default';

const GALLERY_VIEW_MODES = [
  { key: 'single', label: '単一ページ表示' },
  { key: 'rtl-cover', label: '右綴じ(表紙あり)' },
  { key: 'ltr-cover', label: '左綴じ(表紙あり)' },
  { key: 'rtl-nocover', label: '右綴じ(表紙なし)' },
  { key: 'ltr-nocover', label: '左綴じ(表紙なし)' },
];

const galleryDisplayState = {
  mode: 'single',
  modeButton: null,
  modeMenu: null,
  menuOpen: false,
};

const fullscreenState = {
  pseudoEnabled: false,
  container: null,
  button: null,
  exitButton: null,
  nativeSupported: false,
};

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
  if (!document.body || document.body.dataset.galleryPage !== 'true') {
    return;
  }

  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }
    siteStructure = window.siteStructure;

    const params = new URLSearchParams(window.location.search);
    currentGenre = decodeURIComponent(params.get('genre') || '');
    currentSeriesKey = decodeURIComponent(params.get('series') || '');
    currentContentPath = decodeURIComponent(params.get('content') || '');

    if (!currentGenre || !currentSeriesKey || !currentContentPath) {
      showError('ギャラリー情報がありません');
      return;
    }

    currentSeriesData = Series.getEntryByKey(siteStructure, currentGenre, currentSeriesKey);
    if (!currentSeriesData) {
      showError('シリーズが見つかりません');
      return;
    }

    currentGalleries = buildGalleriesForContent(currentContentPath);
    if (currentGalleries.length === 0) {
      showError('ギャラリーが見つかりません');
      return;
    }

    currentGalleryIndex = 0;
    currentGallery = currentGalleries[currentGalleryIndex];
    galleryPages = buildGalleryPages(currentGallery.path, currentGallery);
    galleryDisplayState.mode = loadGalleryViewMode();
    resetBackgroundThumbnailWarmup();

    updateBreadcrumbs();
    renderThumbnailStrip();
    setupNavigation();
    setupDisplayModeControl();
    setupSearch();
    setupZoomInteractions();
    setupThumbnailMode();
    renderCurrentPage();
    renderGalleryPageNav();
  } catch (error) {
    console.error('Error initializing page:', error);
    showError(`ページの読み込みに失敗しました: ${error.message}`);
  }
});

// ============ Data ============

function buildGalleriesForContent(contentPath) {
  const map = window.galleryPagesMap || {};
  const normalized = normalizePath(contentPath);
  if (map[normalized]) return [{ path: normalized }];
  const prefix = normalized + '/';
  return Object.keys(map).filter((k) => k.startsWith(prefix)).sort().map((k) => ({ path: k }));
}

function buildGalleryPages(galleryPath, galleryData) {
  const map = window.galleryPagesMap || {};
  const key = normalizePath(galleryPath);
  const fromMap = map[key];
  const resolver = typeof window.resolveGalleryPageEntries === 'function'
    ? window.resolveGalleryPageEntries
    : (value) => (Array.isArray(value) ? value : []);

  const resolvedPages = resolver(fromMap, `contents/${key}`);

  if (resolvedPages.length > 0) {
    return resolvedPages
      .map((entry) => normalizeGalleryPageEntry(entry, galleryPath))
      .filter((entry) => entry && (entry.image || entry.video));
  }

  if (galleryData && galleryData.thumbnail) {
    return [normalizeGalleryPageEntry({
      type: 'image',
      image: galleryData.thumbnail,
      html: galleryPath,
    }, galleryPath)];
  }

  return [];
}

function normalizeGalleryPageEntry(entry, fallbackHtml) {
  const source = entry || {};
  const htmlPath = resolveAssetPath(source.html || fallbackHtml || '');
  const looksLikeVideo = source.type === 'video' || !!source.video || isVideoPath(source.image) || isVideoPath(source.path);

  if (looksLikeVideo) {
    const rawVideoPath = source.video || source.image || source.path || '';
    return {
      type: 'video',
      video: resolveAssetPath(rawVideoPath),
      html: htmlPath || resolveAssetPath(fallbackHtml || ''),
      thumbNumber: normalizeThumbNumber(source.thumbNumber),
      label: source.label || extractFileStem(rawVideoPath),
      ext: (source.ext || extractExtension(rawVideoPath)).toLowerCase(),
    };
  }

  return {
    type: 'image',
    image: resolveAssetPath(source.image || source.thumbnail || ''),
    thumbnail: resolveAssetPath(source.thumbnail || source.thumb || source.image || ''),
    html: htmlPath || resolveAssetPath(fallbackHtml || ''),
    label: source.label || extractFileStem(source.image || source.thumbnail || ''),
  };
}

function getThumbnailSource(page) {
  return page?.thumbnail || page?.image || '';
}

function normalizeThumbNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function isVideoEntry(entry) {
  return !!entry && entry.type === 'video';
}

function isVideoPath(path) {
  return /\.(avi|mpg|mpeg|mp4|mkv|wmv)$/i.test(String(path || ''));
}

function inferVideoMimeType(path) {
  const normalized = String(path || '').toLowerCase();
  if (normalized.endsWith('.mp4')) return 'video/mp4';
  if (normalized.endsWith('.mpg') || normalized.endsWith('.mpeg')) return 'video/mpeg';
  if (normalized.endsWith('.avi')) return 'video/x-msvideo';
  if (normalized.endsWith('.mkv')) return 'video/x-matroska';
  if (normalized.endsWith('.wmv')) return 'video/x-ms-wmv';
  return '';
}

function normalizePath(path) {
  return String(path || '').replace(/\\/g, '/').replace(/^\/+/, '');
}

function resolveAssetPath(path) {
  const normalized = normalizePath(path);
  if (normalized.startsWith('thumbnail/')) return encodeURI(normalized);
  if (normalized.startsWith('contents/')) return encodeURI(normalized);
  if (normalized.startsWith('photo/')) return encodeURI(`contents/${normalized}`);
  return encodeURI(normalized);
}

function extractFileStem(path) {
  const normalized = normalizePath(path);
  const name = normalized.split('/').pop() || '';
  return name.replace(/\.[^.]+$/, '');
}

function extractExtension(path) {
  const match = String(path || '').match(/\.([^.\\/]+)$/);
  return match ? match[1].toLowerCase() : '';
}

function extractGalleryLabel(path) {
  let parts = String(path || '').replace(/^photo\//, '').split('/');
  parts = parts.slice(1);
  parts = parts.slice(0, -1);
  return parts.join(' / ');
}

function getVideoSequenceNumber(index) {
  let count = 0;
  for (let i = 0; i <= index && i < galleryPages.length; i += 1) {
    if (galleryPages[i] && galleryPages[i].type === 'video') {
      count += 1;
    }
  }
  return count || 1;
}

function normalizeGalleryViewMode(mode) {
  const key = String(mode || '').trim();
  const exists = GALLERY_VIEW_MODES.some((item) => item.key === key);
  return exists ? key : 'single';
}

function getGalleryViewModeLabel(mode) {
  const normalized = normalizeGalleryViewMode(mode);
  const found = GALLERY_VIEW_MODES.find((item) => item.key === normalized);
  return found ? found.label : '単一ページ表示';
}

function isSpreadViewMode(mode) {
  return normalizeGalleryViewMode(mode) !== 'single';
}

function buildSpreadUnits(totalPages, mode) {
  const total = Number(totalPages) || 0;
  if (total <= 0) {
    return [];
  }

  const normalized = normalizeGalleryViewMode(mode);
  if (normalized === 'single') {
    return Array.from({ length: total }, (_, index) => ({
      left: index,
      right: null,
      slots: [index],
      members: [index],
    }));
  }

  const units = [];
  const isRtl = normalized.startsWith('rtl');
  const hasCover = normalized.endsWith('-cover');

  if (hasCover) {
    if (isRtl) {
      units.push({ left: null, right: 0 });
    } else {
      units.push({ left: 0, right: null });
    }
  }

  let cursor = hasCover ? 1 : 0;
  while (cursor < total) {
    if (isRtl) {
      const right = cursor;
      const left = (cursor + 1) < total ? cursor + 1 : null;
      units.push({ left, right });
    } else {
      const left = cursor;
      const right = (cursor + 1) < total ? cursor + 1 : null;
      units.push({ left, right });
    }
    cursor += 2;
  }

  return units.map((unit) => ({
    left: Number.isInteger(unit.left) ? unit.left : null,
    right: Number.isInteger(unit.right) ? unit.right : null,
    slots: [unit.left, unit.right],
    members: [unit.left, unit.right].filter((value) => Number.isInteger(value)),
  }));
}

function getPreferredFocusIndexForSpread(unit, mode) {
  if (!unit || !Array.isArray(unit.members) || unit.members.length === 0) {
    return 0;
  }

  const normalized = normalizeGalleryViewMode(mode);
  if (normalized.startsWith('rtl')) {
    return Number.isInteger(unit.right) ? unit.right : unit.members[0];
  }
  return Number.isInteger(unit.left) ? unit.left : unit.members[0];
}

function getCurrentSpreadInfo() {
  const units = buildSpreadUnits(galleryPages.length, galleryDisplayState.mode);
  if (units.length === 0) {
    return { units: [], unitIndex: -1, unit: null };
  }

  let unitIndex = units.findIndex((candidate) => candidate.members.includes(currentPageIndex));
  if (unitIndex < 0) {
    unitIndex = 0;
  }

  return {
    units,
    unitIndex,
    unit: units[unitIndex],
  };
}

function getActivePageIndexes() {
  const spread = getCurrentSpreadInfo();
  if (!spread.unit) {
    return [];
  }
  return spread.unit.members.slice();
}

function primeThumbnailCache() {
  disposeThumbnailCache();

  thumbnailGenerationToken += 1;
  const token = thumbnailGenerationToken;

  const jobs = [];
  galleryPages.forEach((page, index) => {
    if (isVideoEntry(page)) {
      return;
    }

    const entry = {
      status: 'pending',
      src: '',
      promise: null,
    };

    const taskFactory = () => generateThumbnailSource(page, STAGE_THUMBNAIL_SIZE)
      .then((src) => {
        if (token !== thumbnailGenerationToken) {
          if (src && src.startsWith('blob:')) {
            URL.revokeObjectURL(src);
          }
          return;
        }

        entry.status = 'ready';
        entry.src = src || page.image;
        if (entry.src.startsWith('blob:')) {
          thumbnailCacheState.objectUrls.add(entry.src);
        }
        refreshThumbnailAtIndex(index);
      })
      .catch((error) => {
        console.debug('Thumbnail generation failed:', error);
        if (token !== thumbnailGenerationToken) {
          return;
        }

        entry.status = 'failed';
        entry.src = page.image;
        refreshThumbnailAtIndex(index);
      });

    thumbnailCacheState.entries.set(index, entry);
    jobs.push(() => {
      const running = taskFactory();
      entry.promise = running;
      return running.finally(() => {
        entry.promise = null;
      });
    });
  });

  const parallel = getThumbnailParallelism();
  runWithConcurrency(jobs, parallel).catch((error) => {
    console.debug('Thumbnail queue failed:', error);
  });
}

function getThumbnailParallelism() {
  const hc = Number(window.navigator?.hardwareConcurrency || 4);
  if (!Number.isFinite(hc) || hc <= 1) {
    return 2;
  }
  return Math.max(2, Math.min(4, hc - 1));
}

async function runWithConcurrency(taskFactories, concurrency) {
  if (!Array.isArray(taskFactories) || taskFactories.length === 0) {
    return;
  }

  const queue = taskFactories.slice();
  const workers = [];
  const workerCount = Math.max(1, Math.min(concurrency || 1, queue.length));

  for (let i = 0; i < workerCount; i += 1) {
    workers.push((async () => {
      while (queue.length > 0) {
        const taskFactory = queue.shift();
        if (!taskFactory) {
          continue;
        }
        await taskFactory();
      }
    })());
  }

  await Promise.all(workers);
}

function generateThumbnailSource(page, targetSize) {
  return new Promise((resolve, reject) => {
    const sourceImage = new Image();
    sourceImage.decoding = 'async';
    sourceImage.onload = () => {
      const generate = () => {
        try {
          const srcWidth = sourceImage.naturalWidth || sourceImage.width;
          const srcHeight = sourceImage.naturalHeight || sourceImage.height;
          if (!srcWidth || !srcHeight) {
            resolve(page.image);
            return;
          }

          const canvas = document.createElement('canvas');
          canvas.width = targetSize;
          canvas.height = targetSize;
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            resolve(page.image);
            return;
          }

          const scale = Math.max(targetSize / srcWidth, targetSize / srcHeight);
          const drawWidth = srcWidth * scale;
          const drawHeight = srcHeight * scale;
          const drawX = (targetSize - drawWidth) / 2;
          const drawY = (targetSize - drawHeight) / 2;

          ctx.fillStyle = '#161616';
          ctx.fillRect(0, 0, targetSize, targetSize);
          ctx.drawImage(sourceImage, drawX, drawY, drawWidth, drawHeight);

          canvas.toBlob((blob) => {
            if (!blob) {
              resolve(page.image);
              return;
            }
            resolve(URL.createObjectURL(blob));
          }, 'image/jpeg', 0.78);
        } catch (error) {
          reject(error);
        }
      };

      if (typeof window.requestAnimationFrame === 'function') {
        window.requestAnimationFrame(generate);
      } else {
        generate();
      }
    };
    sourceImage.onerror = () => reject(new Error(`Failed to load ${page.image}`));
    sourceImage.src = page.image;
  });
}

function setupThumbnailCacheDisposal() {
  window.addEventListener('pagehide', disposeThumbnailCache, { once: true });
  window.addEventListener('beforeunload', disposeThumbnailCache, { once: true });
}

function disposeThumbnailCache() {
  thumbnailGenerationToken += 1;
  thumbnailCacheState.entries.clear();
  thumbnailUiState.pendingPanelIndexes.clear();
  thumbnailUiState.panelRefreshScheduled = false;
  for (const url of thumbnailCacheState.objectUrls) {
    try {
      URL.revokeObjectURL(url);
    } catch (error) {
      console.debug('Failed to revoke object URL:', error);
    }
  }
  thumbnailCacheState.objectUrls.clear();
}

function getThumbnailDisplaySrc(index, fallbackSrc) {
  const entry = thumbnailCacheState.entries.get(index);
  if (!entry) {
    return fallbackSrc;
  }
  if (entry.status === 'ready' || entry.status === 'failed') {
    return entry.src || fallbackSrc;
  }
  return fallbackSrc;
}

function refreshThumbnailAtIndex(index) {
  const strip = document.getElementById('thumbList');
  if (strip) {
    const stripItem = strip.querySelector(`.thumb-item[data-index="${index}"] img`);
    if (stripItem && galleryPages[index] && !isVideoEntry(galleryPages[index])) {
      stripItem.src = getThumbnailDisplaySrc(index, galleryPages[index].image);
    }
  }

  if (!galleryPages[index]) {
    return;
  }

  thumbnailUiState.pendingPanelIndexes.add(index);
  scheduleStageThumbnailPanelRefresh();
}

function scheduleStageThumbnailPanelRefresh() {
  if (thumbnailUiState.panelRefreshScheduled) {
    return;
  }

  thumbnailUiState.panelRefreshScheduled = true;
  const prefersIdle = !thumbnailModeState.enabled && typeof window.requestIdleCallback === 'function';
  const schedule = prefersIdle
    ? (callback) => window.requestIdleCallback(callback, { timeout: 120 })
    : (typeof window.requestAnimationFrame === 'function'
      ? window.requestAnimationFrame.bind(window)
      : (callback) => window.setTimeout(callback, 16));

  schedule(() => {
    thumbnailUiState.panelRefreshScheduled = false;
    flushPendingStageThumbnailUpdates();
  });
}

function flushPendingStageThumbnailUpdates() {
  const panel = thumbnailModeState.panel;
  if (!panel || thumbnailUiState.pendingPanelIndexes.size === 0) {
    return;
  }

  const chunkLimit = thumbnailModeState.enabled ? 18 : 8;
  const indexes = Array.from(thumbnailUiState.pendingPanelIndexes).slice(0, chunkLimit);
  indexes.forEach((index) => {
    thumbnailUiState.pendingPanelIndexes.delete(index);
    const panelButton = panel.querySelector(`.stage-thumb-item[data-index="${index}"]`);
    if (panelButton && galleryPages[index]) {
      updateStageThumbnailButton(panelButton, galleryPages[index], index);
    }
  });

  if (thumbnailUiState.pendingPanelIndexes.size > 0) {
    scheduleStageThumbnailPanelRefresh();
  }
}

// ============ Rendering ============

function updateBreadcrumbs() {
  const breadcrumb = document.querySelector('.breadcrumbs-content');
  const genreName = Series.getGenreName(siteStructure, currentGenre);
  const seriesName = currentSeriesData ? (currentSeriesData.name || currentSeriesKey) : currentSeriesKey;
  
  // structure.jsonからコンテンツを検索してnameを取得
  let contentName = '';
  if (currentSeriesData && currentSeriesData.contents) {
    const content = currentSeriesData.contents.find(c => normalizePath(c.path) === normalizePath(currentContentPath));
    if (content && content.name) {
      contentName = content.name;
    }
  }
  // フォールバック
  if (!contentName) {
    contentName = currentGallery ? (currentGallery.name || currentGallery.path || '') : (currentContentPath || '');
  }

  Navigation.renderBreadcrumbs(breadcrumb, [
    { label: 'トップ', href: 'index.html' },
    { label: genreName, href: Series.buildGenreHref(currentGenre), className: 'breadcrumb-genre', id: 'genreLink' },
    { label: seriesName, href: Series.buildSeriesHref(currentGenre, currentSeriesKey), className: 'breadcrumb-series', id: 'seriesLink' },
    { label: contentName, current: true, className: 'breadcrumb-current', id: 'galleryName' }
  ]);
}

function renderCurrentPage() {
  const stage = document.getElementById('photoStage');
  const openOriginalLink = document.getElementById('openOriginalLink');
  const navInfo = document.getElementById('navInfo');

  if (!stage || !openOriginalLink || !navInfo) return;

  if (galleryPages.length === 0) {
    showError('表示できる画像・動画が見つかりません');
    return;
  }

  if (currentPageIndex < 0) currentPageIndex = 0;
  if (currentPageIndex >= galleryPages.length) currentPageIndex = galleryPages.length - 1;

  const spreadInfo = getCurrentSpreadInfo();
  if (!spreadInfo.unit) {
    showError('表示できる画像・動画が見つかりません');
    return;
  }

  if (!spreadInfo.unit.members.includes(currentPageIndex)) {
    currentPageIndex = getPreferredFocusIndexForSpread(spreadInfo.unit, galleryDisplayState.mode);
  }

  const focusedPage = galleryPages[currentPageIndex];
  resetZoomState();
  renderStageContent(stage, spreadInfo);

  if (focusedPage && isVideoEntry(focusedPage)) {
    openOriginalLink.href = focusedPage.video || focusedPage.html || '#';
    openOriginalLink.textContent = '動画ファイルを別タブで開く';
  } else {
    openOriginalLink.href = (focusedPage && focusedPage.html) || '#';
    openOriginalLink.textContent = '元のHTMLを別タブで開く';
  }
  openOriginalLink.target = '_blank';
  openOriginalLink.rel = 'noopener noreferrer';

  const modeLabel = getGalleryViewModeLabel(galleryDisplayState.mode);
  if (isSpreadViewMode(galleryDisplayState.mode)) {
    const pageText = spreadInfo.unit.members.map((index) => String(index + 1)).join(' / ');
    navInfo.textContent = `${pageText} / ${galleryPages.length} (${modeLabel})`;
  } else {
    navInfo.textContent = `${currentPageIndex + 1} / ${galleryPages.length} (${focusedPage && isVideoEntry(focusedPage) ? '動画' : '画像'})`;
  }

  updateNavigationButtons();
  updateActiveThumbnail();
  updateActiveStageThumbnail();
}

function renderStageContent(stage, spreadInfo) {
  const existing = stage.querySelector('.media-stage-root');
  if (existing) {
    existing.remove();
  }

  if (!spreadInfo || !spreadInfo.unit) return;

  if (!isSpreadViewMode(galleryDisplayState.mode)) {
    const page = galleryPages[currentPageIndex];
    renderSingleStageContent(stage, page);
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'media-stage-content media-stage-root is-spread';

  spreadInfo.unit.slots.forEach((pageIndex, slotIndex) => {
    const side = slotIndex === 0 ? 'left' : 'right';
    wrapper.appendChild(createSpreadPane(pageIndex, side));
  });

  stage.prepend(wrapper);
  setZoomSpread(wrapper);
}

function renderSingleStageContent(stage, page) {
  if (!page) return;

  if (isVideoEntry(page)) {
    const wrapper = document.createElement('div');
    wrapper.className = 'media-stage-content media-stage-root is-video';

    const video = document.createElement('video');
    video.className = 'media-stage-video';
    video.controls = true;
    video.preload = 'metadata';
    video.autoplay = true;
    video.playsInline = true;

    const source = document.createElement('source');
    source.src = page.video;
    const mime = inferVideoMimeType(page.video);
    if (mime) {
      source.type = mime;
    }
    video.appendChild(source);

    const note = document.createElement('p');
    note.className = 'media-note';

    const prefix = document.createElement('span');
    prefix.textContent = '再生できない場合は ';

    const link = document.createElement('a');
    link.href = page.video;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = '動画ファイルを別タブで開いてください';

    const suffix = document.createElement('span');
    suffix.textContent = '。';

    if (mime && typeof video.canPlayType === 'function' && video.canPlayType(mime) === '') {
      note.classList.add('is-warning');
      prefix.textContent = 'この形式はブラウザで再生できない場合があります。';
      suffix.textContent = '';
    }

    note.appendChild(prefix);
    note.appendChild(link);
    note.appendChild(suffix);

    video.addEventListener('error', () => {
      note.classList.add('is-warning');
      prefix.textContent = 'この動画はブラウザで再生できません。';
      suffix.textContent = '';
    });

    wrapper.appendChild(video);
    wrapper.appendChild(note);
    stage.prepend(wrapper);
    setZoomMedia(null);
    video.load();
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'media-stage-content media-stage-root is-image';

  const img = document.createElement('img');
  img.id = 'photoImage';
  img.className = 'media-stage-image';
  img.src = page.image;
  img.alt = `${currentGallery ? (currentGallery.name || currentGallery.path || '') : ''} ${currentPageIndex + 1}`;

  wrapper.appendChild(img);
  stage.prepend(wrapper);
  setZoomMedia(img);
}

function createSpreadPane(pageIndex, side) {
  const pane = document.createElement('div');
  pane.className = 'media-stage-pane';
  if (side === 'left') {
    pane.classList.add('is-spread-left');
  } else if (side === 'right') {
    pane.classList.add('is-spread-right');
  }

  if (!Number.isInteger(pageIndex) || !galleryPages[pageIndex]) {
    pane.classList.add('is-empty');
    pane.setAttribute('aria-hidden', 'true');
    return pane;
  }

  const page = galleryPages[pageIndex];

  if (isVideoEntry(page)) {
    const video = document.createElement('video');
    video.className = 'media-stage-video';
    video.controls = true;
    video.preload = 'metadata';
    video.autoplay = true;
    video.playsInline = true;

    const source = document.createElement('source');
    source.src = page.video;
    const mime = inferVideoMimeType(page.video);
    if (mime) {
      source.type = mime;
    }
    video.appendChild(source);
    pane.appendChild(video);
    video.load();
    return pane;
  }

  const img = document.createElement('img');
  img.className = 'media-stage-spread-image';
  img.src = page.image;
  img.alt = `${currentGallery ? (currentGallery.name || currentGallery.path || '') : ''} ${pageIndex + 1}`;
  pane.appendChild(img);
  return pane;
}

function renderThumbnailStrip() {
  const strip = document.getElementById('thumbList');
  if (!strip) return;

  strip.innerHTML = '';

  galleryPages.forEach((page, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'thumb-item';
    button.setAttribute('data-index', String(index));

    if (isVideoEntry(page)) {
      button.classList.add('is-video');
      button.setAttribute('aria-label', `動画 ${index + 1}`);
      button.title = `${page.label || '動画'} (${(page.ext || extractExtension(page.video) || 'video').toUpperCase()})`;
      button.appendChild(buildVideoThumbnail(page, index));
    } else {
      button.setAttribute('aria-label', `画像 ${index + 1}`);

      const img = document.createElement('img');
      img.src = getThumbnailSource(page);
      img.alt = `サムネイル ${index + 1}`;
      img.loading = 'lazy';
      img.decoding = 'async';
      button.appendChild(img);
    }

    button.addEventListener('click', () => {
      currentPageIndex = index;
      renderCurrentPage();
    });

    strip.appendChild(button);
  });

  strip.addEventListener('wheel', (event) => {
    event.preventDefault();
    strip.scrollTop += event.deltaY;
  }, { passive: false });

  renderStageThumbnailPanel();
}

function buildVideoThumbnail(page, index) {
  const wrapper = document.createElement('div');
  wrapper.className = 'video-thumb';

  const number = document.createElement('span');
  number.className = 'video-thumb-number';
  number.textContent = String(page.thumbNumber || getVideoSequenceNumber(index));

  const icon = document.createElement('span');
  icon.className = 'video-thumb-icon';
  icon.textContent = '▶';

  const label = document.createElement('span');
  label.className = 'video-thumb-label';
  label.textContent = 'VIDEO';

  const ext = document.createElement('span');
  ext.className = 'video-thumb-ext';
  ext.textContent = (page.ext || extractExtension(page.video) || 'video').toUpperCase();

  wrapper.appendChild(number);
  wrapper.appendChild(icon);
  wrapper.appendChild(label);
  wrapper.appendChild(ext);
  return wrapper;
}

function updateActiveThumbnail() {
  const strip = document.getElementById('thumbList');
  if (!strip) return;

  const activeIndexes = new Set(getActivePageIndexes());
  const buttons = strip.querySelectorAll('.thumb-item');
  buttons.forEach((btn) => {
    const index = Number.parseInt(btn.getAttribute('data-index') || '-1', 10);
    btn.classList.toggle('is-active', activeIndexes.has(index));
  });

  const focusIndex = currentPageIndex;
  const focusButton = strip.querySelector(`.thumb-item[data-index="${focusIndex}"]`);
  if (!focusButton) return;
  focusButton.scrollIntoView({ block: 'nearest' });
}

function setupThumbnailMode() {
  thumbnailModeState.panel = document.getElementById('stageThumbnailPanel');
  thumbnailModeState.toggle = document.getElementById('thumbModeToggle');
  thumbnailModeState.busyOverlay = document.getElementById('stageModeBusy');

  if (!thumbnailModeState.panel || !thumbnailModeState.toggle || !thumbnailModeState.busyOverlay) {
    return;
  }

  // Keep panel in render tree to avoid expensive re-layout on reopen.
  thumbnailModeState.panel.hidden = false;

  ensureVirtualPanelContent();
  thumbnailModeState.panel.addEventListener('scroll', scheduleVirtualThumbnailRender, { passive: true });
  window.addEventListener('resize', scheduleVirtualThumbnailRender);

  thumbnailModeState.toggle.addEventListener('pointerdown', (event) => {
    event.stopPropagation();
  });

  thumbnailModeState.toggle.addEventListener('click', () => {
    if (thumbnailModeState.enabled) {
      setThumbnailMode(false);
      return;
    }

    setThumbnailMode(true);
  });

  renderStageThumbnailPanel();
  updateThumbModeToggle();
}

function renderStageThumbnailPanel() {
  const panel = thumbnailModeState.panel;
  if (!panel) {
    return;
  }

  ensureVirtualPanelContent();
  thumbnailVirtualState.content.innerHTML = '';
  thumbnailVirtualState.startIndex = -1;
  thumbnailVirtualState.endIndex = -1;
  thumbnailModeState.activeThumbButton = null;

  thumbnailUiState.pendingPanelIndexes.clear();
  renderVirtualThumbnailWindow(true);
  updateActiveStageThumbnail();
}

function ensureVirtualPanelContent() {
  const panel = thumbnailModeState.panel;
  if (!panel) {
    return;
  }

  let content = panel.querySelector('.stage-thumbnail-virtual-content');
  if (!content) {
    content = document.createElement('div');
    content.className = 'stage-thumbnail-virtual-content';
    panel.appendChild(content);
  }
  thumbnailVirtualState.content = content;
}

function scheduleVirtualThumbnailRender() {
  if (thumbnailVirtualState.rafScheduled) {
    return;
  }

  thumbnailVirtualState.rafScheduled = true;
  const frame = typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame.bind(window)
    : (callback) => window.setTimeout(callback, 16);

  frame(() => {
    thumbnailVirtualState.rafScheduled = false;
    renderVirtualThumbnailWindow(false);
  });
}

function getVirtualThumbnailMetrics() {
  const panel = thumbnailModeState.panel;
  if (!panel) {
    return null;
  }

  const styles = window.getComputedStyle(panel);
  const minSize = Number.parseInt(styles.getPropertyValue('--stage-thumb-min'), 10) || 76;
  const gap = Number.parseInt(styles.getPropertyValue('--stage-thumb-gap'), 10) || 10;
  const paddingLeft = Number.parseFloat(styles.paddingLeft) || 0;
  const paddingRight = Number.parseFloat(styles.paddingRight) || 0;
  const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
  const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
  const viewportWidth = Math.max(1, panel.clientWidth - paddingLeft - paddingRight);

  const columns = Math.max(1, Math.floor((viewportWidth + gap) / (minSize + gap)));
  const totalGap = Math.max(0, (columns - 1) * gap);
  const cellSize = Math.max(40, Math.floor((viewportWidth - totalGap) / columns));
  const rowCount = Math.ceil(galleryPages.length / columns);
  const contentHeight = (rowCount * cellSize) + (Math.max(0, rowCount - 1) * gap) + paddingTop + paddingBottom;

  return {
    columns,
    gap,
    cellSize,
    paddingLeft,
    paddingTop,
    viewportHeight: panel.clientHeight,
    scrollTop: panel.scrollTop,
    contentHeight,
  };
}

function renderVirtualThumbnailWindow(force) {
  const panel = thumbnailModeState.panel;
  const content = thumbnailVirtualState.content;
  const metrics = getVirtualThumbnailMetrics();
  if (!panel || !content || !metrics) {
    return;
  }

  thumbnailVirtualState.columns = metrics.columns;
  thumbnailVirtualState.cellSize = metrics.cellSize;
  thumbnailVirtualState.gap = metrics.gap;
  content.style.height = `${Math.max(metrics.contentHeight, panel.clientHeight)}px`;

  if (galleryPages.length === 0) {
    content.innerHTML = '';
    thumbnailVirtualState.startIndex = -1;
    thumbnailVirtualState.endIndex = -1;
    thumbnailModeState.activeThumbButton = null;
    return;
  }

  const rowHeight = metrics.cellSize + metrics.gap;
  const startRow = Math.max(0, Math.floor(metrics.scrollTop / Math.max(1, rowHeight)) - 2);
  const endRow = Math.max(startRow, Math.ceil((metrics.scrollTop + metrics.viewportHeight) / Math.max(1, rowHeight)) + 2);
  const startIndex = Math.max(0, startRow * metrics.columns);
  const endIndex = Math.min(galleryPages.length - 1, ((endRow + 1) * metrics.columns) - 1);

  if (!force && startIndex === thumbnailVirtualState.startIndex && endIndex === thumbnailVirtualState.endIndex) {
    return;
  }

  thumbnailVirtualState.startIndex = startIndex;
  thumbnailVirtualState.endIndex = endIndex;

  const fragment = document.createDocumentFragment();
  for (let index = startIndex; index <= endIndex; index += 1) {
    const page = galleryPages[index];
    if (!page) {
      continue;
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'stage-thumb-item';
    button.setAttribute('data-index', String(index));
    button.title = isVideoEntry(page) ? `動画 ${index + 1}` : `画像 ${index + 1}`;

    const row = Math.floor(index / metrics.columns);
    const col = index % metrics.columns;
    const left = metrics.paddingLeft + (col * (metrics.cellSize + metrics.gap));
    const top = metrics.paddingTop + (row * (metrics.cellSize + metrics.gap));
    button.style.left = `${left}px`;
    button.style.top = `${top}px`;
    button.style.width = `${metrics.cellSize}px`;
    button.style.height = `${metrics.cellSize}px`;

    updateStageThumbnailButton(button, page, index);

    if (index === currentPageIndex) {
      button.classList.add('is-active');
      thumbnailModeState.activeThumbButton = button;
    }

    button.addEventListener('click', () => {
      currentPageIndex = index;
      renderCurrentPage();
      setThumbnailMode(false);
    });

    fragment.appendChild(button);
  }

  content.innerHTML = '';
  content.appendChild(fragment);

  if (!content.querySelector(`.stage-thumb-item[data-index="${currentPageIndex}"]`)) {
    thumbnailModeState.activeThumbButton = null;
  }
}

function updateStageThumbnailButton(button, page, index) {
  button.innerHTML = '';
  button.classList.remove('is-video');

  if (isVideoEntry(page)) {
    button.classList.add('is-video');
    return;
  }

  const img = document.createElement('img');
  img.src = getThumbnailSource(page);
  img.alt = `サムネイル ${index + 1}`;
  img.loading = 'lazy';
  img.decoding = 'async';
  button.appendChild(img);
}

function updateActiveStageThumbnail() {
  const panel = thumbnailModeState.panel;
  if (!panel) {
    return;
  }

  renderVirtualThumbnailWindow(false);

  const activeIndexes = new Set(getActivePageIndexes());
  const visibleButtons = panel.querySelectorAll('.stage-thumb-item');
  visibleButtons.forEach((button) => {
    const index = Number.parseInt(button.getAttribute('data-index') || '-1', 10);
    button.classList.toggle('is-active', activeIndexes.has(index));
  });

  const active = panel.querySelector(`.stage-thumb-item[data-index="${currentPageIndex}"]`);
  if (!active) {
    if (thumbnailModeState.enabled && !thumbnailModeState.suppressAutoScrollOnce) {
      scrollActiveThumbnailIntoView();
      renderVirtualThumbnailWindow(true);
    }

    thumbnailModeState.activeThumbButton = null;
    return;
  }

  thumbnailModeState.activeThumbButton = active;
  if (thumbnailModeState.enabled) {
    if (thumbnailModeState.suppressAutoScrollOnce) {
      thumbnailModeState.suppressAutoScrollOnce = false;
    } else {
      scrollActiveThumbnailIntoView();
    }
  }
}

function scrollActiveThumbnailIntoView() {
  const panel = thumbnailModeState.panel;
  const metrics = getVirtualThumbnailMetrics();
  if (!panel || !metrics) {
    return;
  }

  const row = Math.floor(currentPageIndex / Math.max(1, metrics.columns));
  const rowTop = metrics.paddingTop + (row * (metrics.cellSize + metrics.gap));
  const rowBottom = rowTop + metrics.cellSize;
  const viewTop = panel.scrollTop;
  const viewBottom = panel.scrollTop + panel.clientHeight;

  if (rowTop < viewTop) {
    panel.scrollTop = Math.max(0, rowTop - metrics.gap);
    scheduleVirtualThumbnailRender();
    return;
  }

  if (rowBottom > viewBottom) {
    panel.scrollTop = Math.max(0, rowBottom - panel.clientHeight + metrics.gap);
    scheduleVirtualThumbnailRender();
  }
}

function setThumbnailMode(enabled) {
  const stage = document.getElementById('photoStage');
  const panel = thumbnailModeState.panel;
  if (!stage || !panel || !thumbnailModeState.busyOverlay) {
    return;
  }

  thumbnailModeState.transitionToken += 1;
  const token = thumbnailModeState.transitionToken;

  thumbnailModeState.enabled = !!enabled;
  stage.classList.toggle('is-thumbnail-mode', thumbnailModeState.enabled);

  if (thumbnailModeState.enabled) {
    thumbnailModeState.suppressAutoScrollOnce = true;
    setThumbnailModeBusyVisible(true);
    scheduleAfterPaint(() => {
      if (!thumbnailModeState.enabled || token !== thumbnailModeState.transitionToken) {
        return;
      }
      updateActiveStageThumbnail();

      if (thumbnailModeState.hasOpenedOnce) {
        // Re-open should be immediate; avoid repeating expensive readiness checks.
        setThumbnailModeBusyVisible(false);
        startBackgroundThumbnailWarmup();
        return;
      }

      thumbnailModeState.hasOpenedOnce = true;
      finalizeThumbnailModeTransition(token);
    });
  } else {
    setThumbnailModeBusyVisible(false);
  }

  updateThumbModeToggle();
}

function setThumbnailModeBusyVisible(visible) {
  const overlay = thumbnailModeState.busyOverlay;
  if (!overlay) {
    return;
  }

  overlay.hidden = !visible;
  overlay.setAttribute('aria-hidden', visible ? 'false' : 'true');
}

function finalizeThumbnailModeTransition(token) {
  const panel = thumbnailModeState.panel;
  if (!panel) {
    setThumbnailModeBusyVisible(false);
    return;
  }

  const frame = typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame.bind(window)
    : (callback) => window.setTimeout(callback, 16);

  frame(() => {
    frame(async () => {
      await waitForVisibleThumbnailImages(panel, 4, 700);

      if (!thumbnailModeState.enabled || token !== thumbnailModeState.transitionToken) {
        return;
      }
      setThumbnailModeBusyVisible(false);
      startBackgroundThumbnailWarmup();
    });
  });
}

function resetBackgroundThumbnailWarmup() {
  thumbnailWarmupState.sessionId += 1;
  thumbnailWarmupState.running = false;
  thumbnailWarmupState.cursor = 0;
  thumbnailWarmupState.inflight = 0;
  thumbnailWarmupState.loadedSources.clear();
}

function startBackgroundThumbnailWarmup() {
  if (thumbnailWarmupState.running) {
    return;
  }

  if (thumbnailWarmupState.cursor >= galleryPages.length) {
    return;
  }

  thumbnailWarmupState.running = true;
  scheduleBackgroundThumbnailWarmup();
}

function scheduleBackgroundThumbnailWarmup() {
  if (!thumbnailWarmupState.running) {
    return;
  }

  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(() => {
      runBackgroundThumbnailWarmupStep();
    }, { timeout: 180 });
    return;
  }

  window.setTimeout(() => {
    runBackgroundThumbnailWarmupStep();
  }, 24);
}

function runBackgroundThumbnailWarmupStep() {
  if (!thumbnailWarmupState.running) {
    thumbnailWarmupState.running = false;
    return;
  }

  const maxPerStep = 5;
  let processed = 0;

  while (
    processed < maxPerStep
    && thumbnailWarmupState.cursor < galleryPages.length
    && thumbnailWarmupState.inflight < thumbnailWarmupState.maxInflight
  ) {
    const index = thumbnailWarmupState.cursor;
    thumbnailWarmupState.cursor += 1;
    processed += 1;

    const page = galleryPages[index];
    if (!page || isVideoEntry(page) || !getThumbnailSource(page)) {
      continue;
    }

    const thumbSrc = getThumbnailSource(page);

    if (thumbnailWarmupState.loadedSources.has(thumbSrc)) {
      continue;
    }

    thumbnailWarmupState.loadedSources.add(thumbSrc);
    thumbnailWarmupState.inflight += 1;

    const img = new Image();
    img.decoding = 'async';

    const done = () => {
      img.onload = null;
      img.onerror = null;
      thumbnailWarmupState.inflight = Math.max(0, thumbnailWarmupState.inflight - 1);

      if (!thumbnailWarmupState.running) {
        return;
      }

      if (thumbnailWarmupState.cursor >= galleryPages.length && thumbnailWarmupState.inflight === 0) {
        thumbnailWarmupState.running = false;
        return;
      }

      scheduleBackgroundThumbnailWarmup();
    };

    img.onload = done;
    img.onerror = done;
    img.src = thumbSrc;
  }

  if (thumbnailWarmupState.cursor >= galleryPages.length && thumbnailWarmupState.inflight === 0) {
    thumbnailWarmupState.running = false;
    return;
  }

  scheduleBackgroundThumbnailWarmup();
}

function scheduleAfterPaint(callback) {
  const frame = typeof window.requestAnimationFrame === 'function'
    ? window.requestAnimationFrame.bind(window)
    : (cb) => window.setTimeout(cb, 16);
  frame(() => {
    frame(callback);
  });
}

function waitForVisibleThumbnailImages(panel, sampleCount, timeoutMs) {
  const images = Array.from(panel.querySelectorAll('.stage-thumb-item img')).slice(0, sampleCount);
  if (images.length === 0) {
    return Promise.resolve();
  }

  const waits = images.map((img) => {
    if (img.complete && img.naturalWidth > 0) {
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      const done = () => {
        img.removeEventListener('load', done);
        img.removeEventListener('error', done);
        resolve();
      };
      img.addEventListener('load', done, { once: true });
      img.addEventListener('error', done, { once: true });
    });
  });

  const allLoaded = Promise.all(waits);
  const timeout = new Promise((resolve) => {
    window.setTimeout(resolve, timeoutMs);
  });

  return Promise.race([allLoaded, timeout]);
}

function updateThumbModeToggle() {
  const toggle = thumbnailModeState.toggle;
  if (!toggle) {
    return;
  }

  toggle.classList.toggle('is-thumbnail-mode', thumbnailModeState.enabled);
  toggle.setAttribute('aria-pressed', thumbnailModeState.enabled ? 'true' : 'false');
  toggle.setAttribute('aria-label', thumbnailModeState.enabled ? '画像表示に戻す' : '全サムネイルを表示');
}

// ============ Zoom / Pan ============

function setupZoomInteractions() {
  zoomState.stage = document.getElementById('photoStage');
  zoomState.control = document.getElementById('zoomControl');
  zoomState.slider = document.getElementById('zoomSlider');
  zoomState.valueLabel = document.getElementById('zoomValue');

  if (!zoomState.stage) return;

  if (typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 0) {
    zoomState.stage.style.touchAction = 'none';
  }

  if (zoomState.slider) {
    zoomState.slider.min = '0';
    zoomState.slider.max = String(ZOOM_LEVELS.length - 1);
    zoomState.slider.step = '1';
    zoomState.slider.value = String(getZoomLevelIndexByPercent(zoomState.percent));

    zoomState.slider.addEventListener('input', () => {
      const requestedIndex = Math.round(Number(zoomState.slider.value));
      const safeIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, requestedIndex));
      const nextPercent = ZOOM_LEVELS[safeIndex];
      showTransientZoomControl();
      setZoomPercent(nextPercent);
    });

    zoomState.slider.addEventListener('pointerdown', () => {
      showTransientZoomControl({ keepVisible: true });
    });
  }

  zoomState.stage.addEventListener('wheel', handleStageWheel, { passive: false });
  zoomState.stage.addEventListener('pointerdown', handlePinchPointerDown);
  zoomState.stage.addEventListener('pointerdown', handleSwipeNavigationStart);
  zoomState.stage.addEventListener('pointerdown', handlePanStart);
  document.addEventListener('pointermove', handlePinchPointerMove);
  document.addEventListener('pointermove', handleSwipeNavigationMove);
  document.addEventListener('pointermove', handlePanMove);
  document.addEventListener('pointerup', handlePinchPointerEnd);
  document.addEventListener('pointerup', handleSwipeNavigationEnd);
  document.addEventListener('pointerup', handlePanEnd);
  document.addEventListener('pointercancel', handlePinchPointerEnd);
  document.addEventListener('pointercancel', handleSwipeNavigationEnd);
  document.addEventListener('pointercancel', handlePanEnd);
  window.addEventListener('resize', handleViewportChanged);
  document.addEventListener('fullscreenchange', handleViewportChanged);

  setZoomControlEnabled(false);
  updateZoomIndicator();
}

function setZoomMedia(imageElement) {
  zoomState.activeImage = imageElement || null;
  zoomState.spreadWrapper = null;
  zoomState.percent = ZOOM_MIN_PERCENT;
  zoomState.panX = 0;
  zoomState.panY = 0;
  zoomState.isDragging = false;
  zoomState.pointerId = null;
  resetPinchState();

  if (!zoomState.activeImage) {
    setZoomControlEnabled(false);
    updateZoomIndicator();
    updateZoomCssState();
    return;
  }

  setZoomControlEnabled(true);
  updateZoomIndicator();
  applyZoomTransform();

  if (zoomState.activeImage.complete) {
    handleViewportChanged();
  } else {
    zoomState.activeImage.addEventListener('load', handleViewportChanged, { once: true });
  }
}

function setZoomSpread(wrapperElement) {
  zoomState.activeImage = null;
  zoomState.spreadWrapper = wrapperElement || null;
  zoomState.percent = ZOOM_MIN_PERCENT;
  zoomState.panX = 0;
  zoomState.panY = 0;
  zoomState.isDragging = false;
  zoomState.pointerId = null;
  resetPinchState();

  if (!zoomState.spreadWrapper) {
    setZoomControlEnabled(false);
    updateZoomIndicator();
    updateZoomCssState();
    return;
  }

  setZoomControlEnabled(true);
  updateZoomIndicator();
  applyZoomTransform();
}

function resetZoomState() {
  zoomState.percent = ZOOM_MIN_PERCENT;
  zoomState.panX = 0;
  zoomState.panY = 0;
  zoomState.isDragging = false;
  zoomState.pointerId = null;
  resetPinchState();
  updateZoomIndicator();
  applyZoomTransform();
}

function handleStageWheel(event) {
  if (thumbnailModeState.enabled) {
    return;
  }

  if (!ensureZoomableImageForInteraction()) {
    return;
  }

  event.preventDefault();
  showTransientZoomControl();

  const direction = event.deltaY < 0 ? 1 : -1;
  const nextPercent = getAdjacentZoomPercent(zoomState.percent, direction);
  setZoomPercent(nextPercent, {
    anchorClientX: event.clientX,
    anchorClientY: event.clientY,
  });
}

function setZoomPercent(nextPercent, options = {}) {
  if (!zoomState.activeImage && !zoomState.spreadWrapper && !ensureZoomableImageForInteraction()) {
    updateZoomIndicator();
    return;
  }

  const previousPercent = zoomState.percent;
  const previousScale = previousPercent / 100;
  const snappedPercent = getClosestZoomPercent(nextPercent);
  const clamped = Math.min(ZOOM_MAX_PERCENT, Math.max(ZOOM_MIN_PERCENT, snappedPercent));

  zoomState.percent = clamped;
  const nextScale = zoomState.percent / 100;

  if (
    zoomState.stage
    && typeof options.anchorClientX === 'number'
    && typeof options.anchorClientY === 'number'
    && previousScale > 0
    && nextScale !== previousScale
  ) {
    const rect = zoomState.stage.getBoundingClientRect();
    const anchorOffsetX = options.anchorClientX - (rect.left + (rect.width / 2));
    const anchorOffsetY = options.anchorClientY - (rect.top + (rect.height / 2));
    const ratio = nextScale / previousScale;

    zoomState.panX = (ratio * zoomState.panX) + ((1 - ratio) * anchorOffsetX);
    zoomState.panY = (ratio * zoomState.panY) + ((1 - ratio) * anchorOffsetY);
  }

  if (zoomState.percent <= ZOOM_MIN_PERCENT) {
    zoomState.panX = 0;
    zoomState.panY = 0;
    zoomState.isDragging = false;
    zoomState.pointerId = null;
  }

  clampPanOffsets();
  applyZoomTransform();
  updateZoomIndicator();
}

function ensureZoomableImageForInteraction() {
  return !!(zoomState.activeImage || zoomState.spreadWrapper);
}

function handlePanStart(event) {
  if (zoomState.isPinching || (event.pointerType === 'touch' && zoomState.touchPoints.size > 1)) return;
  if ((!zoomState.activeImage && !zoomState.spreadWrapper) || zoomState.percent <= ZOOM_MIN_PERCENT) return;
  if (event.button !== 0) return;
  if (event.target && typeof event.target.closest === 'function' && event.target.closest('#zoomControl')) return;
  if (thumbnailModeState.enabled) return;
  if (event.target && typeof event.target.closest === 'function') {
    if (event.target.closest('#stageThumbnailPanel')) return;
    if (event.target.closest('#thumbModeToggle')) return;
  }

  zoomState.isDragging = true;
  zoomState.pointerId = event.pointerId;
  zoomState.dragStartX = event.clientX;
  zoomState.dragStartY = event.clientY;
  zoomState.dragOriginPanX = zoomState.panX;
  zoomState.dragOriginPanY = zoomState.panY;

  if (zoomState.stage && typeof zoomState.stage.setPointerCapture === 'function') {
    try {
      zoomState.stage.setPointerCapture(event.pointerId);
    } catch (error) {
      console.debug('Pointer capture not available:', error);
    }
  }

  applyZoomTransform();
  event.preventDefault();
}

function handleSwipeNavigationStart(event) {
  if (!canStartSwipeNavigation(event)) {
    return;
  }

  swipeNavState.tracking = true;
  swipeNavState.pointerId = event.pointerId;
  swipeNavState.startX = event.clientX;
  swipeNavState.startY = event.clientY;
  swipeNavState.lastX = event.clientX;
  swipeNavState.lastY = event.clientY;
  swipeNavState.startTimeMs = Date.now();
  swipeNavState.axis = 'none';
}

function handleSwipeNavigationMove(event) {
  if (zoomState.isPinching) {
    return;
  }
  if (!swipeNavState.tracking || swipeNavState.pointerId !== event.pointerId) {
    return;
  }

  swipeNavState.lastX = event.clientX;
  swipeNavState.lastY = event.clientY;

  const deltaX = swipeNavState.lastX - swipeNavState.startX;
  const deltaY = swipeNavState.lastY - swipeNavState.startY;
  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);

  if (swipeNavState.axis === 'none' && (absX >= 12 || absY >= 12)) {
    if (absX >= absY * 1.05) {
      swipeNavState.axis = 'x';
    } else if (absY > absX * 1.05) {
      swipeNavState.axis = 'y';
    }
  }

  // 開始位置は表示ステージ基準で判定する。
  const zones = getSwipeNavigationZones();
  const isLeftEdge = swipeNavState.startX <= zones.leftEdgeMaxX;
  const isRightEdge = swipeNavState.startX >= zones.rightEdgeMinX;
  const isNavigationArea = isLeftEdge || isRightEdge;

  // navigation領域またはX軸動きの場合のみpreventDefault
  if ((isNavigationArea || swipeNavState.axis === 'x') && event.cancelable) {
    event.preventDefault();
  }
}

function handleSwipeNavigationEnd(event) {
  if (!swipeNavState.tracking || swipeNavState.pointerId !== event.pointerId) {
    return;
  }

  swipeNavState.tracking = false;

  if (event.type === 'pointercancel') {
    swipeNavState.pointerId = null;
    swipeNavState.axis = 'none';
    return;
  }

  const deltaX = event.clientX - swipeNavState.startX;
  const deltaY = event.clientY - swipeNavState.startY;
  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);
  const resolvedAxis = swipeNavState.axis;
  const zones = getSwipeNavigationZones();

  swipeNavState.pointerId = null;
  swipeNavState.axis = 'none';

  // 中央エリアでの上下動きの場合はナビゲーションしない（ブラウザスクロール優先）
  const isCenterArea = swipeNavState.startX > zones.leftEdgeMaxX && swipeNavState.startX < zones.rightEdgeMinX;
  if (isCenterArea && resolvedAxis === 'y') {
    return;
  }

  // ゾーン判定はタップ終了位置ではなく開始位置で固定する。
  const isLeftEdge = swipeNavState.startX <= zones.leftEdgeMaxX;
  const isRightEdge = swipeNavState.startX >= zones.rightEdgeMinX;

  // タップだけで判定（動きが小さい場合）、またはスワイプ（移動が大きい場合）で対応
  const isTap = absX < 12 && absY < 12;
  const isHorizontalSwipe = absX >= 24;

  if (isTap && !isLeftEdge && !isRightEdge && maybeHandleCenterDoubleTap(event.clientX, event.clientY)) {
    return;
  }

  if (isRightEdge && (isTap || isHorizontalSwipe)) {
    navigateNextPage();
  } else if (isLeftEdge && (isTap || isHorizontalSwipe)) {
    navigatePrevPage();
  }
}

function getSwipeNavigationZones() {
  const fallbackWidth = Math.max(1, window.innerWidth || 1);
  const fallbackZone = fallbackWidth * 0.12;
  const fallbackLeft = fallbackZone;
  const fallbackRight = fallbackWidth - fallbackZone;

  if (!zoomState.stage) {
    return {
      leftEdgeMaxX: fallbackLeft,
      rightEdgeMinX: fallbackRight,
    };
  }

  const rect = zoomState.stage.getBoundingClientRect();
  const stageWidth = Math.max(1, rect.width || 0);
  if (!Number.isFinite(stageWidth) || stageWidth <= 1) {
    return {
      leftEdgeMaxX: fallbackLeft,
      rightEdgeMinX: fallbackRight,
    };
  }

  const zoneWidth = Math.max(44, stageWidth * 0.12);
  return {
    leftEdgeMaxX: rect.left + zoneWidth,
    rightEdgeMinX: rect.right - zoneWidth,
  };
}

function maybeHandleCenterDoubleTap(clientX, clientY) {
  if (!isCenterDoubleTapArea(clientX, clientY)) {
    resetCenterDoubleTapState();
    return false;
  }

  const now = Date.now();
  const isWithinTime = (now - zoomState.lastCenterTapTimeMs) <= 320;
  const dx = clientX - zoomState.lastCenterTapX;
  const dy = clientY - zoomState.lastCenterTapY;
  const isWithinDistance = Math.hypot(dx, dy) <= 34;

  zoomState.lastCenterTapTimeMs = now;
  zoomState.lastCenterTapX = clientX;
  zoomState.lastCenterTapY = clientY;

  if (!isWithinTime || !isWithinDistance) {
    return false;
  }

  resetCenterDoubleTapState();
  setZoomPercent(ZOOM_MIN_PERCENT);
  showTransientZoomControl();
  return true;
}

function isCenterDoubleTapArea(clientX, clientY) {
  if (!zoomState.stage) {
    return false;
  }

  const rect = zoomState.stage.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return false;
  }

  const centerZoneWidth = rect.width * 0.52;
  const centerZoneHeight = rect.height * 0.62;
  const left = rect.left + ((rect.width - centerZoneWidth) / 2);
  const right = rect.right - ((rect.width - centerZoneWidth) / 2);
  const top = rect.top + ((rect.height - centerZoneHeight) / 2);
  const bottom = rect.bottom - ((rect.height - centerZoneHeight) / 2);

  return clientX >= left && clientX <= right && clientY >= top && clientY <= bottom;
}

function resetCenterDoubleTapState() {
  zoomState.lastCenterTapTimeMs = 0;
  zoomState.lastCenterTapX = 0;
  zoomState.lastCenterTapY = 0;
}

function canStartSwipeNavigation(event) {
  if (!zoomState.stage || !zoomState.stage.contains(event.target)) return false;
  if (event.pointerType !== 'touch') return false;
  if (!event.isPrimary) return false;
  if (zoomState.isPinching) return false;
  if (zoomState.touchPoints.size > 1) return false;
  if (thumbnailModeState.enabled) return false;
  if (zoomState.isDragging) return false;
  if (zoomState.percent > ZOOM_MIN_PERCENT) return false;

  if (event.target && typeof event.target.closest === 'function') {
    if (event.target.closest('#zoomControl')) return false;
    if (event.target.closest('#thumbModeToggle')) return false;
    if (event.target.closest('#stageThumbnailPanel')) return false;
  }

  return true;
}

function handlePanMove(event) {
  if (zoomState.isPinching) return;
  if (!zoomState.isDragging || zoomState.pointerId !== event.pointerId) return;

  const deltaX = event.clientX - zoomState.dragStartX;
  const deltaY = event.clientY - zoomState.dragStartY;
  zoomState.panX = zoomState.dragOriginPanX + deltaX;
  zoomState.panY = zoomState.dragOriginPanY + deltaY;

  clampPanOffsets();
  applyZoomTransform();
}

function handlePanEnd(event) {
  if (!zoomState.isDragging || zoomState.pointerId !== event.pointerId) return;

  if (zoomState.stage && typeof zoomState.stage.releasePointerCapture === 'function') {
    try {
      zoomState.stage.releasePointerCapture(event.pointerId);
    } catch (error) {
      console.debug('Pointer release not available:', error);
    }
  }

  zoomState.isDragging = false;
  zoomState.pointerId = null;
  applyZoomTransform();
}

function handleViewportChanged() {
  if (!zoomState.activeImage && !zoomState.spreadWrapper) return;
  clampPanOffsets();
  applyZoomTransform();
}

function clampPanOffsets() {
  const target = zoomState.activeImage || zoomState.spreadWrapper;
  if (!target || !zoomState.stage) return;
  if (zoomState.percent <= ZOOM_MIN_PERCENT) {
    zoomState.panX = 0;
    zoomState.panY = 0;
    return;
  }

  const baseWidth = target.clientWidth;
  const baseHeight = target.clientHeight;
  if (!baseWidth || !baseHeight) return;

  const stageWidth = zoomState.stage.clientWidth;
  const stageHeight = zoomState.stage.clientHeight;

  const scale = zoomState.percent / 100;
  const scaledWidth = baseWidth * scale;
  const scaledHeight = baseHeight * scale;

  const maxPanX = Math.max(0, (scaledWidth - stageWidth) / 2);
  const maxPanY = Math.max(0, (scaledHeight - stageHeight) / 2);

  zoomState.panX = Math.max(-maxPanX, Math.min(maxPanX, zoomState.panX));
  zoomState.panY = Math.max(-maxPanY, Math.min(maxPanY, zoomState.panY));
}

function applyZoomTransform() {
  const target = zoomState.activeImage || zoomState.spreadWrapper;
  if (!target) {
    updateZoomCssState();
    return;
  }

  const scale = zoomState.percent / 100;
  target.style.transform = `translate(${zoomState.panX}px, ${zoomState.panY}px) scale(${scale})`;
  updateZoomCssState();
}

function updateZoomCssState() {
  const target = zoomState.activeImage || zoomState.spreadWrapper;
  if (zoomState.stage) {
    const zoomable = !!target && zoomState.percent > ZOOM_MIN_PERCENT;
    zoomState.stage.classList.toggle('is-zoomable', zoomable);
    zoomState.stage.classList.toggle('is-dragging', zoomState.isDragging);
  }

  if (target) {
    target.classList.toggle('is-dragging', zoomState.isDragging);
  }
}

function updateZoomIndicator() {
  if (zoomState.slider) {
    zoomState.slider.value = String(getZoomLevelIndexByPercent(zoomState.percent));
  }

  if (zoomState.valueLabel) {
    zoomState.valueLabel.textContent = `${zoomState.percent}%`;
  }
}

function getClosestZoomPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return ZOOM_MIN_PERCENT;

  return ZOOM_LEVELS.reduce((closest, level) => {
    return Math.abs(level - numeric) < Math.abs(closest - numeric) ? level : closest;
  }, ZOOM_LEVELS[0]);
}

function getZoomLevelIndexByPercent(percent) {
  const snappedPercent = getClosestZoomPercent(percent);
  const index = ZOOM_LEVELS.indexOf(snappedPercent);
  return index >= 0 ? index : 0;
}

function getAdjacentZoomPercent(currentPercent, direction) {
  const currentIndex = getZoomLevelIndexByPercent(currentPercent);
  const step = direction > 0 ? 1 : -1;
  const nextIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, currentIndex + step));
  return ZOOM_LEVELS[nextIndex];
}

function setZoomControlEnabled(enabled) {
  if (zoomState.slider) {
    zoomState.slider.disabled = !enabled;
  }

  if (zoomState.control) {
    zoomState.control.setAttribute('aria-disabled', enabled ? 'false' : 'true');
  }

  if (!enabled) {
    hideTransientZoomControl(true);
  }
}

function resetPinchState() {
  zoomState.touchPoints.clear();
  zoomState.isPinching = false;
  zoomState.pinchStartDistance = 0;
  zoomState.pinchStartPercent = zoomState.percent;
  resetCenterDoubleTapState();
}

function isCompactViewport() {
  return window.matchMedia('(max-width: 768px)').matches;
}

function showTransientZoomControl(options = {}) {
  if (!zoomState.control || !isCompactViewport()) {
    return;
  }

  zoomState.control.classList.add('is-transient-visible');

  if (zoomState.controlFadeTimer) {
    window.clearTimeout(zoomState.controlFadeTimer);
    zoomState.controlFadeTimer = null;
  }

  if (!options.keepVisible) {
    zoomState.controlFadeTimer = window.setTimeout(() => {
      hideTransientZoomControl();
    }, 1400);
  }
}

function hideTransientZoomControl(force = false) {
  if (!zoomState.control) {
    return;
  }

  if (zoomState.controlFadeTimer) {
    window.clearTimeout(zoomState.controlFadeTimer);
    zoomState.controlFadeTimer = null;
  }

  if (force || isCompactViewport()) {
    zoomState.control.classList.remove('is-transient-visible');
  }
}

function handlePinchPointerDown(event) {
  if (event.pointerType !== 'touch') {
    return;
  }

  zoomState.touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });

  if (zoomState.touchPoints.size >= 2) {
    initializePinchGesture();
    if (event.cancelable) {
      event.preventDefault();
    }
  }
}

function handlePinchPointerMove(event) {
  if (event.pointerType !== 'touch') {
    return;
  }

  if (!zoomState.touchPoints.has(event.pointerId)) {
    return;
  }

  zoomState.touchPoints.set(event.pointerId, { x: event.clientX, y: event.clientY });

  if (zoomState.touchPoints.size < 2) {
    return;
  }

  if (!zoomState.isPinching) {
    initializePinchGesture();
  }

  const points = getFirstTwoTouchPoints();
  if (!points) {
    return;
  }

  const distance = getTouchDistance(points[0], points[1]);
  if (distance <= 0 || zoomState.pinchStartDistance <= 0) {
    return;
  }

  const nextPercent = zoomState.pinchStartPercent * (distance / zoomState.pinchStartDistance);
  const anchorClientX = (points[0].x + points[1].x) / 2;
  const anchorClientY = (points[0].y + points[1].y) / 2;

  setZoomPercent(nextPercent, { anchorClientX, anchorClientY });
  showTransientZoomControl({ keepVisible: true });

  if (event.cancelable) {
    event.preventDefault();
  }
}

function handlePinchPointerEnd(event) {
  if (event.pointerType !== 'touch') {
    return;
  }

  zoomState.touchPoints.delete(event.pointerId);

  if (zoomState.isPinching && zoomState.touchPoints.size < 2) {
    zoomState.isPinching = false;
    zoomState.pinchStartDistance = 0;
    zoomState.pinchStartPercent = zoomState.percent;
    showTransientZoomControl();
  }
}

function initializePinchGesture() {
  if (!ensureZoomableImageForInteraction()) {
    return;
  }

  const points = getFirstTwoTouchPoints();
  if (!points) {
    return;
  }

  const distance = getTouchDistance(points[0], points[1]);
  if (distance <= 0) {
    return;
  }

  zoomState.isPinching = true;
  zoomState.pinchStartDistance = distance;
  zoomState.pinchStartPercent = zoomState.percent;

  swipeNavState.tracking = false;
  swipeNavState.pointerId = null;
  swipeNavState.axis = 'none';

  if (zoomState.isDragging) {
    zoomState.isDragging = false;
    zoomState.pointerId = null;
    applyZoomTransform();
  }

  showTransientZoomControl({ keepVisible: true });
}

function getFirstTwoTouchPoints() {
  const points = Array.from(zoomState.touchPoints.values());
  if (points.length < 2) {
    return null;
  }
  return [points[0], points[1]];
}

function getTouchDistance(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.hypot(dx, dy);
}

// ============ Display Mode ============

function setupDisplayModeControl() {
  galleryDisplayState.modeButton = document.getElementById('spreadModeButton');
  galleryDisplayState.modeMenu = document.getElementById('spreadModeMenu');

  if (!galleryDisplayState.modeButton || !galleryDisplayState.modeMenu) {
    return;
  }

  renderDisplayModeMenu();
  updateDisplayModeButton();

  galleryDisplayState.modeButton.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleDisplayModeMenu();
  });

  galleryDisplayState.modeMenu.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  document.addEventListener('click', (event) => {
    if (!galleryDisplayState.menuOpen) {
      return;
    }

    const control = galleryDisplayState.modeButton ? galleryDisplayState.modeButton.closest('.spread-mode-control') : null;
    if (control && control.contains(event.target)) {
      return;
    }
    closeDisplayModeMenu();
  });
}

function renderDisplayModeMenu() {
  const menu = galleryDisplayState.modeMenu;
  if (!menu) {
    return;
  }

  menu.innerHTML = '';
  GALLERY_VIEW_MODES.forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'spread-mode-menu-item';
    button.textContent = item.label;
    button.setAttribute('role', 'menuitemradio');
    button.setAttribute('aria-checked', item.key === galleryDisplayState.mode ? 'true' : 'false');
    if (item.key === galleryDisplayState.mode) {
      button.classList.add('is-active');
    }

    button.addEventListener('click', () => {
      applyGalleryViewMode(item.key, true);
      closeDisplayModeMenu();
    });

    menu.appendChild(button);
  });
}

function updateDisplayModeButton() {
  if (!galleryDisplayState.modeButton) {
    return;
  }

  galleryDisplayState.modeButton.textContent = getGalleryViewModeLabel(galleryDisplayState.mode);
}

function openDisplayModeMenu() {
  if (!galleryDisplayState.modeMenu || !galleryDisplayState.modeButton) {
    return;
  }

  galleryDisplayState.menuOpen = true;
  galleryDisplayState.modeMenu.hidden = false;
  galleryDisplayState.modeButton.setAttribute('aria-expanded', 'true');
}

function closeDisplayModeMenu() {
  if (!galleryDisplayState.modeMenu || !galleryDisplayState.modeButton) {
    return;
  }

  galleryDisplayState.menuOpen = false;
  galleryDisplayState.modeMenu.hidden = true;
  galleryDisplayState.modeButton.setAttribute('aria-expanded', 'false');
}

function toggleDisplayModeMenu() {
  if (galleryDisplayState.menuOpen) {
    closeDisplayModeMenu();
  } else {
    openDisplayModeMenu();
  }
}

function applyGalleryViewMode(mode, persist) {
  const normalized = normalizeGalleryViewMode(mode);

  if (normalized === galleryDisplayState.mode) {
    renderDisplayModeMenu();
    updateDisplayModeButton();
    return;
  }

  galleryDisplayState.mode = normalized;
  renderDisplayModeMenu();
  updateDisplayModeButton();

  if (persist) {
    persistGalleryViewMode(galleryDisplayState.mode);
  }

  renderCurrentPage();
}

function loadGalleryViewMode() {
  try {
    const currentScopeKey = getGalleryViewModeStorageKey();
    const currentScopeStored = window.localStorage.getItem(currentScopeKey);
    if (currentScopeStored !== null) {
      return normalizeGalleryViewMode(currentScopeStored);
    }

    // Smartphone mode is isolated, but on first run reuse the default scope if it exists.
    if (getGalleryViewModeScope() === GALLERY_VIEW_MODE_SCOPE_SMARTPHONE) {
      const defaultScopeKey = getGalleryViewModeStorageKeyByScope(GALLERY_VIEW_MODE_SCOPE_DEFAULT);
      const defaultStored = window.localStorage.getItem(defaultScopeKey);
      if (defaultStored !== null) {
        return normalizeGalleryViewMode(defaultStored);
      }
    }

    // Backward compatibility: previously this setting was global.
    const legacy = window.localStorage.getItem(GALLERY_VIEW_MODE_LEGACY_STORAGE_KEY);
    return normalizeGalleryViewMode(legacy);
  } catch (error) {
    console.debug('Failed to load gallery view mode:', error);
    return 'single';
  }
}

function persistGalleryViewMode(mode) {
  try {
    const key = getGalleryViewModeStorageKey();
    window.localStorage.setItem(key, normalizeGalleryViewMode(mode));
  } catch (error) {
    console.debug('Failed to persist gallery view mode:', error);
  }
}

function getGalleryViewModeStorageKey() {
  return getGalleryViewModeStorageKeyByScope(getGalleryViewModeScope());
}

function getGalleryViewModeStorageKeyByScope(scope) {
  const normalizedScope = scope === GALLERY_VIEW_MODE_SCOPE_SMARTPHONE
    ? GALLERY_VIEW_MODE_SCOPE_SMARTPHONE
    : GALLERY_VIEW_MODE_SCOPE_DEFAULT;
  const contentPath = normalizePath(currentContentPath || currentGallery?.path || '');
  if (!contentPath) {
    return `${GALLERY_VIEW_MODE_STORAGE_KEY_PREFIX}:${normalizedScope}`;
  }
  return `${GALLERY_VIEW_MODE_STORAGE_KEY_PREFIX}:${normalizedScope}:${contentPath}`;
}

function getGalleryViewModeScope() {
  return isSmartphoneDeviceForViewMode() ? GALLERY_VIEW_MODE_SCOPE_SMARTPHONE : GALLERY_VIEW_MODE_SCOPE_DEFAULT;
}

function isSmartphoneDeviceForViewMode() {
  const ua = navigator.userAgent || '';
  const isMobileUa = /iPhone|iPod|Android.+Mobile|Windows Phone|webOS|BlackBerry|Opera Mini|IEMobile/i.test(ua);
  if (isMobileUa) {
    return true;
  }

  const touchCapable = typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 0;
  if (!touchCapable) {
    return false;
  }

  const shortEdge = Math.min(window.screen?.width || window.innerWidth || 0, window.screen?.height || window.innerHeight || 0);
  return shortEdge > 0 && shortEdge <= 540;
}

// ============ Navigation ============

function setupNavigation() {
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');
  const fullscreenToggle = document.getElementById('fullscreenToggle');
  const pseudoFullscreenExit = document.getElementById('pseudoFullscreenExit');

  fullscreenState.container = document.getElementById('photoViewer');
  fullscreenState.button = fullscreenToggle;
  fullscreenState.exitButton = pseudoFullscreenExit;
  fullscreenState.nativeSupported = canUseGalleryFullscreen();

  if (prevButton) prevButton.addEventListener('click', navigatePrevPage);
  if (nextButton) nextButton.addEventListener('click', navigateNextPage);
  if (fullscreenToggle) {
    fullscreenToggle.addEventListener('click', toggleFullscreen);
    syncFullscreenButtonState();
  }
  if (pseudoFullscreenExit) {
    pseudoFullscreenExit.addEventListener('click', () => {
      exitGalleryFullscreen();
    });
  }

  document.addEventListener('fullscreenchange', handleFullscreenChange);
  window.addEventListener('resize', updatePseudoFullscreenViewportHeight);
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', updatePseudoFullscreenViewportHeight);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (fullscreenState.pseudoEnabled || isNativeFullscreenActive())) {
      exitGalleryFullscreen();
      return;
    }

    if (e.key === 'Escape' && galleryDisplayState.menuOpen) {
      closeDisplayModeMenu();
      return;
    }

    if (e.key === 'Escape' && thumbnailModeState.enabled) {
      setThumbnailMode(false);
      return;
    }

    if (e.key === 'ArrowLeft') navigatePrevPage();
    if (e.key === 'ArrowRight') navigateNextPage();
    if (e.key.toLowerCase() === 'f') toggleFullscreen();
  });
}

function canUseGalleryFullscreen() {
  const container = document.getElementById('photoViewer');
  if (!container) return false;

  const userAgent = navigator.userAgent || '';
  const isIPhoneSafari = /iPhone/.test(userAgent)
    && /Safari/.test(userAgent)
    && !/CriOS|FxiOS|EdgiOS/.test(userAgent);

  if (isIPhoneSafari) {
    return false;
  }

  return Boolean(document.fullscreenEnabled && typeof container.requestFullscreen === 'function');
}

function navigatePrevPage() {
  const spread = getCurrentSpreadInfo();
  if (isSpreadViewMode(galleryDisplayState.mode) && spread.unitIndex >= 0) {
    if (spread.unitIndex > 0) {
      const prevUnit = spread.units[spread.unitIndex - 1];
      currentPageIndex = getPreferredFocusIndexForSpread(prevUnit, galleryDisplayState.mode);
      renderCurrentPage();
      return;
    }
  } else if (currentPageIndex > 0) {
    currentPageIndex -= 1;
    renderCurrentPage();
    return;
  }

  if (currentGalleryIndex > 0) {
    loadGalleryByIndex(currentGalleryIndex - 1, 'last');
  }
}

function navigateNextPage() {
  const spread = getCurrentSpreadInfo();
  if (isSpreadViewMode(galleryDisplayState.mode) && spread.unitIndex >= 0) {
    if (spread.unitIndex < spread.units.length - 1) {
      const nextUnit = spread.units[spread.unitIndex + 1];
      currentPageIndex = getPreferredFocusIndexForSpread(nextUnit, galleryDisplayState.mode);
      renderCurrentPage();
      return;
    }
  } else if (currentPageIndex < galleryPages.length - 1) {
    currentPageIndex += 1;
    renderCurrentPage();
    return;
  }

  if (currentGalleryIndex < currentGalleries.length - 1) {
    loadGalleryByIndex(currentGalleryIndex + 1, 0);
  }
}

function updateNavigationButtons() {
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');

  const spread = getCurrentSpreadInfo();
  const atFirstMedia = isSpreadViewMode(galleryDisplayState.mode)
    ? spread.unitIndex <= 0
    : currentPageIndex <= 0;
  const atLastMedia = isSpreadViewMode(galleryDisplayState.mode)
    ? spread.unitIndex >= spread.units.length - 1
    : currentPageIndex >= galleryPages.length - 1;

  if (prevButton) prevButton.disabled = atFirstMedia && currentGalleryIndex <= 0;
  if (nextButton) nextButton.disabled = atLastMedia && currentGalleryIndex >= currentGalleries.length - 1;
}

function loadGalleryByIndex(galleryIndex, startAt) {
  if (galleryIndex < 0 || galleryIndex >= currentGalleries.length) return;

  currentGalleryIndex = galleryIndex;
  currentGallery = currentGalleries[currentGalleryIndex];
  galleryPages = buildGalleryPages(currentGallery.path, currentGallery);

  if (startAt === 'last') {
    currentPageIndex = Math.max(0, galleryPages.length - 1);
  } else {
    currentPageIndex = 0;
  }

  resetBackgroundThumbnailWarmup();

  if (thumbnailModeState.enabled) {
    thumbnailModeState.enabled = false;
    const stage = document.getElementById('photoStage');
    if (stage) stage.classList.remove('is-thumbnail-mode');
    updateThumbModeToggle();
  }
  thumbnailModeState.hasOpenedOnce = false;

  updateBreadcrumbs();
  renderThumbnailStrip();
  renderCurrentPage();
  renderGalleryPageNav();
}

function renderGalleryPageNav() {
  const container = document.getElementById('galleryPageNav');
  if (!container) return;

  container.innerHTML = '';

  if (!currentGalleries || currentGalleries.length <= 1) return;

  const prevBtn = document.createElement('button');
  prevBtn.type = 'button';
  prevBtn.className = 'page-nav-btn';
  prevBtn.textContent = '←';
  prevBtn.setAttribute('aria-label', '前のページへ');
  prevBtn.disabled = currentGalleryIndex <= 0;
  if (!prevBtn.disabled) {
    prevBtn.addEventListener('click', () => loadGalleryByIndex(currentGalleryIndex - 1, 0));
  }
  container.appendChild(prevBtn);

  currentGalleries.forEach((_, index) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'page-nav-btn' + (index === currentGalleryIndex ? ' is-current' : '');
    btn.textContent = String(index + 1);
    btn.setAttribute('aria-label', `ページ ${index + 1}`);
    if (index === currentGalleryIndex) {
      btn.setAttribute('aria-current', 'page');
    } else {
      btn.addEventListener('click', () => loadGalleryByIndex(index, 0));
    }
    container.appendChild(btn);
  });

  const nextBtn = document.createElement('button');
  nextBtn.type = 'button';
  nextBtn.className = 'page-nav-btn';
  nextBtn.textContent = '→';
  nextBtn.setAttribute('aria-label', '次のページへ');
  nextBtn.disabled = currentGalleryIndex >= currentGalleries.length - 1;
  if (!nextBtn.disabled) {
    nextBtn.addEventListener('click', () => loadGalleryByIndex(currentGalleryIndex + 1, 0));
  }
  container.appendChild(nextBtn);
}

async function toggleFullscreen() {
  const container = fullscreenState.container || document.getElementById('photoViewer');
  const button = fullscreenState.button || document.getElementById('fullscreenToggle');
  if (!container || !button) return;

  fullscreenState.container = container;
  fullscreenState.button = button;
  fullscreenState.nativeSupported = canUseGalleryFullscreen();

  if (fullscreenState.pseudoEnabled || isNativeFullscreenActive()) {
    await exitGalleryFullscreen();
    return;
  }

  try {
    if (fullscreenState.nativeSupported) {
      await container.requestFullscreen();
      syncFullscreenButtonState();
    } else {
      enterPseudoFullscreen();
    }
  } catch (error) {
    console.debug('Fullscreen API not available. Using pseudo fullscreen:', error);
    enterPseudoFullscreen();
  }
}

function isNativeFullscreenActive() {
  return !!(fullscreenState.container && document.fullscreenElement === fullscreenState.container);
}

async function exitGalleryFullscreen() {
  if (fullscreenState.pseudoEnabled) {
    exitPseudoFullscreen();
    return;
  }

  if (isNativeFullscreenActive() && typeof document.exitFullscreen === 'function') {
    try {
      await document.exitFullscreen();
    } catch (error) {
      console.debug('Failed to exit Fullscreen API:', error);
    }
  }

  syncFullscreenButtonState();
}

function enterPseudoFullscreen() {
  const container = fullscreenState.container;
  if (!container) {
    return;
  }

  fullscreenState.pseudoEnabled = true;
  document.body.classList.add('gallery-pseudo-fullscreen-active');
  container.classList.add('is-pseudo-fullscreen');
  updatePseudoFullscreenViewportHeight();
  syncFullscreenButtonState();
  handleViewportChanged();
}

function exitPseudoFullscreen() {
  if (!fullscreenState.pseudoEnabled) {
    return;
  }

  fullscreenState.pseudoEnabled = false;
  document.body.classList.remove('gallery-pseudo-fullscreen-active');
  if (fullscreenState.container) {
    fullscreenState.container.classList.remove('is-pseudo-fullscreen');
  }
  document.documentElement.style.removeProperty('--gallery-fullscreen-vh');
  syncFullscreenButtonState();
  handleViewportChanged();
}

function updatePseudoFullscreenViewportHeight() {
  if (!fullscreenState.pseudoEnabled) {
    return;
  }

  const viewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
  if (!Number.isFinite(viewportHeight) || viewportHeight <= 0) {
    return;
  }

  document.documentElement.style.setProperty('--gallery-fullscreen-vh', `${Math.round(viewportHeight)}px`);
}

function handleFullscreenChange() {
  if (fullscreenState.pseudoEnabled && document.fullscreenElement) {
    exitPseudoFullscreen();
    return;
  }

  syncFullscreenButtonState();
  handleViewportChanged();
}

function syncFullscreenButtonState() {
  const button = fullscreenState.button || document.getElementById('fullscreenToggle');
  const pseudoExitButton = fullscreenState.exitButton || document.getElementById('pseudoFullscreenExit');
  const container = fullscreenState.container || document.getElementById('photoViewer');
  const active = fullscreenState.pseudoEnabled || isNativeFullscreenActive();
  const showOverlayExit = active && shouldShowOverlayExitButton();

  if (pseudoExitButton) {
    pseudoExitButton.hidden = !showOverlayExit;
  }

  if (container) {
    container.classList.toggle('is-overlay-exit-visible', showOverlayExit);
  }

  if (!button) {
    return;
  }

  button.textContent = active ? '全画面解除' : '全画面';
  button.setAttribute('aria-pressed', active ? 'true' : 'false');
}

function shouldShowOverlayExitButton() {
  const hasTouch = typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 0;
  if (!hasTouch) {
    return false;
  }

  if (window.matchMedia('(pointer: coarse)').matches) {
    return true;
  }

  return window.matchMedia('(hover: none)').matches;
}

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;
  searchInput.placeholder = Search.getSearchPlaceholder(siteStructure, currentGenre, true);

  const navigateToSearch = () => {
    const query = searchInput.value.trim();
    if (!query) return;
    window.location.href = 'index.html?genre=' + encodeURIComponent(currentGenre) + '&q=' + encodeURIComponent(query);
  };

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      navigateToSearch();
    }
    if (e.key === 'Escape') {
      searchInput.value = '';
    }
  });
}

// ============ Utilities ============

function showError(message) {
  const viewer = document.getElementById('photoViewer');
  if (!viewer) return;
  viewer.innerHTML = `<div class="photo-error">${message}</div>`;
}

window.GalleryUtils = {
  buildSpreadUnits,
  buildGalleryPages,
  extractExtension,
  getGalleryViewModeLabel,
  inferVideoMimeType,
  isVideoPath,
  normalizeGalleryViewMode,
  normalizeGalleryPageEntry,
  normalizePath,
  resolveAssetPath,
};
