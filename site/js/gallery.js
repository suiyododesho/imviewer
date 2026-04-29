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
  stage: null,
  control: null,
  slider: null,
  valueLabel: null,
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
    resetBackgroundThumbnailWarmup();

    updateBreadcrumbs();
    renderThumbnailStrip();
    setupNavigation();
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

  if (Array.isArray(fromMap) && fromMap.length > 0) {
    return fromMap
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
  const contentName = currentGallery ? (currentGallery.name || currentGallery.path || '') : (currentContentPath || '');

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

  const page = galleryPages[currentPageIndex];
  resetZoomState();
  renderStageContent(stage, page);

  if (isVideoEntry(page)) {
    openOriginalLink.href = page.video || page.html || '#';
    openOriginalLink.textContent = '動画ファイルを別タブで開く';
  } else {
    openOriginalLink.href = page.html || '#';
    openOriginalLink.textContent = '元のHTMLを別タブで開く';
  }
  openOriginalLink.target = '_blank';
  openOriginalLink.rel = 'noopener noreferrer';

  navInfo.textContent = `${currentPageIndex + 1} / ${galleryPages.length} (${isVideoEntry(page) ? '動画' : '画像'})`;
  updateNavigationButtons();
  updateActiveThumbnail();
  updateActiveStageThumbnail();
}

function renderStageContent(stage, page) {
  const existing = stage.querySelector('.media-stage-root');
  if (existing) {
    existing.remove();
  }

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

  const buttons = strip.querySelectorAll('.thumb-item');
  buttons.forEach((btn) => btn.classList.remove('is-active'));

  const active = strip.querySelector(`.thumb-item[data-index="${currentPageIndex}"]`);
  if (!active) return;

  active.classList.add('is-active');
  active.scrollIntoView({ block: 'nearest' });
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

  const active = panel.querySelector(`.stage-thumb-item[data-index="${currentPageIndex}"]`);
  if (!active) {
    if (thumbnailModeState.enabled && !thumbnailModeState.suppressAutoScrollOnce) {
      scrollActiveThumbnailIntoView();
      renderVirtualThumbnailWindow(true);
    }

    if (thumbnailModeState.activeThumbButton) {
      thumbnailModeState.activeThumbButton.classList.remove('is-active');
      thumbnailModeState.activeThumbButton = null;
    }
    return;
  }

  if (thumbnailModeState.activeThumbButton && thumbnailModeState.activeThumbButton !== active) {
    thumbnailModeState.activeThumbButton.classList.remove('is-active');
  }

  active.classList.add('is-active');
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

  if (zoomState.slider) {
    zoomState.slider.min = '0';
    zoomState.slider.max = String(ZOOM_LEVELS.length - 1);
    zoomState.slider.step = '1';
    zoomState.slider.value = String(getZoomLevelIndexByPercent(zoomState.percent));

    zoomState.slider.addEventListener('input', () => {
      const requestedIndex = Math.round(Number(zoomState.slider.value));
      const safeIndex = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, requestedIndex));
      const nextPercent = ZOOM_LEVELS[safeIndex];
      setZoomPercent(nextPercent);
    });
  }

  zoomState.stage.addEventListener('wheel', handleStageWheel, { passive: false });
  zoomState.stage.addEventListener('pointerdown', handleSwipeNavigationStart);
  zoomState.stage.addEventListener('pointerdown', handlePanStart);
  document.addEventListener('pointermove', handleSwipeNavigationMove);
  document.addEventListener('pointermove', handlePanMove);
  document.addEventListener('pointerup', handleSwipeNavigationEnd);
  document.addEventListener('pointerup', handlePanEnd);
  document.addEventListener('pointercancel', handleSwipeNavigationEnd);
  document.addEventListener('pointercancel', handlePanEnd);
  window.addEventListener('resize', handleViewportChanged);
  document.addEventListener('fullscreenchange', handleViewportChanged);

  setZoomControlEnabled(false);
  updateZoomIndicator();
}

function setZoomMedia(imageElement) {
  zoomState.activeImage = imageElement || null;
  zoomState.percent = ZOOM_MIN_PERCENT;
  zoomState.panX = 0;
  zoomState.panY = 0;
  zoomState.isDragging = false;
  zoomState.pointerId = null;

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

function resetZoomState() {
  zoomState.percent = ZOOM_MIN_PERCENT;
  zoomState.panX = 0;
  zoomState.panY = 0;
  zoomState.isDragging = false;
  zoomState.pointerId = null;
  updateZoomIndicator();
  applyZoomTransform();
}

function handleStageWheel(event) {
  if (!zoomState.activeImage) return;

  if (thumbnailModeState.enabled) {
    return;
  }

  event.preventDefault();

  const direction = event.deltaY < 0 ? 1 : -1;
  const nextPercent = getAdjacentZoomPercent(zoomState.percent, direction);
  setZoomPercent(nextPercent, {
    anchorClientX: event.clientX,
    anchorClientY: event.clientY,
  });
}

function setZoomPercent(nextPercent, options = {}) {
  if (!zoomState.activeImage) {
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

function handlePanStart(event) {
  if (!zoomState.activeImage || zoomState.percent <= ZOOM_MIN_PERCENT) return;
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

  if (swipeNavState.axis === 'x' && event.cancelable) {
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
  const elapsedMs = Date.now() - swipeNavState.startTimeMs;

  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);

  const isQuickFlick = elapsedMs <= 260
    && absX >= 24
    && absX >= absY * 0.9;

  const isSwipe = elapsedMs <= 950
    && absX >= 48
    && absY <= 96
    && absX >= absY * 0.95;

  const isValidSwipe = swipeNavState.axis !== 'y' && (isQuickFlick || isSwipe);

  swipeNavState.pointerId = null;
  swipeNavState.axis = 'none';

  if (!isValidSwipe) {
    return;
  }

  if (deltaX < 0) {
    navigateNextPage();
  } else {
    navigatePrevPage();
  }
}

function canStartSwipeNavigation(event) {
  if (!zoomState.stage || !zoomState.stage.contains(event.target)) return false;
  if (event.pointerType !== 'touch') return false;
  if (!event.isPrimary) return false;
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
  if (!zoomState.activeImage) return;
  clampPanOffsets();
  applyZoomTransform();
}

function clampPanOffsets() {
  if (!zoomState.activeImage || !zoomState.stage) return;
  if (zoomState.percent <= ZOOM_MIN_PERCENT) {
    zoomState.panX = 0;
    zoomState.panY = 0;
    return;
  }

  const baseWidth = zoomState.activeImage.clientWidth;
  const baseHeight = zoomState.activeImage.clientHeight;
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
  if (!zoomState.activeImage) {
    updateZoomCssState();
    return;
  }

  const scale = zoomState.percent / 100;
  zoomState.activeImage.style.transform = `translate(${zoomState.panX}px, ${zoomState.panY}px) scale(${scale})`;
  updateZoomCssState();
}

function updateZoomCssState() {
  if (zoomState.stage) {
    const zoomable = !!zoomState.activeImage && zoomState.percent > ZOOM_MIN_PERCENT;
    zoomState.stage.classList.toggle('is-zoomable', zoomable);
    zoomState.stage.classList.toggle('is-dragging', zoomState.isDragging);
  }

  if (zoomState.activeImage) {
    zoomState.activeImage.classList.toggle('is-dragging', zoomState.isDragging);
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
}

// ============ Navigation ============

function setupNavigation() {
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');
  const fullscreenToggle = document.getElementById('fullscreenToggle');
  const fullscreenSupported = canUseGalleryFullscreen();

  if (prevButton) prevButton.addEventListener('click', navigatePrevPage);
  if (nextButton) nextButton.addEventListener('click', navigateNextPage);
  if (fullscreenToggle) {
    if (fullscreenSupported) {
      fullscreenToggle.addEventListener('click', toggleFullscreen);
    } else {
      fullscreenToggle.hidden = true;
    }
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && thumbnailModeState.enabled) {
      setThumbnailMode(false);
      return;
    }

    if (e.key === 'ArrowLeft') navigatePrevPage();
    if (e.key === 'ArrowRight') navigateNextPage();
    if (fullscreenSupported && e.key.toLowerCase() === 'f') toggleFullscreen();
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
  if (currentPageIndex > 0) {
    currentPageIndex -= 1;
    renderCurrentPage();
  } else if (currentGalleryIndex > 0) {
    loadGalleryByIndex(currentGalleryIndex - 1, 'last');
  }
}

function navigateNextPage() {
  if (currentPageIndex < galleryPages.length - 1) {
    currentPageIndex += 1;
    renderCurrentPage();
  } else if (currentGalleryIndex < currentGalleries.length - 1) {
    loadGalleryByIndex(currentGalleryIndex + 1, 0);
  }
}

function updateNavigationButtons() {
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');

  if (prevButton) prevButton.disabled = currentPageIndex <= 0 && currentGalleryIndex <= 0;
  if (nextButton) nextButton.disabled = currentPageIndex >= galleryPages.length - 1 && currentGalleryIndex >= currentGalleries.length - 1;
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
  const container = document.getElementById('photoViewer');
  const button = document.getElementById('fullscreenToggle');
  if (!container || !button || !canUseGalleryFullscreen()) return;

  try {
    if (!document.fullscreenElement) {
      await container.requestFullscreen();
      button.textContent = '全画面解除';
      button.setAttribute('aria-pressed', 'true');
    } else {
      await document.exitFullscreen();
      button.textContent = '全画面';
      button.setAttribute('aria-pressed', 'false');
    }
  } catch (error) {
    console.debug('Fullscreen API not available:', error);
  }
}

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const query = e.target.value;
    if (query.trim().length > 0) {
      window.location.href = 'index.html';
    }
  });

  searchInput.addEventListener('keydown', (e) => {
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
  buildGalleryPages,
  extractExtension,
  inferVideoMimeType,
  isVideoPath,
  normalizeGalleryPageEntry,
  normalizePath,
  resolveAssetPath,
};
