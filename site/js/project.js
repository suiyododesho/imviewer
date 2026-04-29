/**
 * Project Page Main Script
 * Handles display of all people and galleries for a specific project.
 */

let siteStructure = null;
let currentProject = null;
let currentProjectData = null;
let currentSeries = '';

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }

    siteStructure = window.siteStructure;

    const params = new URLSearchParams(window.location.search);
    currentProject = decodeURIComponent(params.get('project') || '');
    if (!currentProject) {
      showError('企画情報がありません');
      return;
    }

    if (!siteStructure[currentProject]) {
      showError('企画が見つかりません');
      return;
    }

    currentProjectData = siteStructure[currentProject];
    currentSeries = Series.getProjectSeries(currentProjectData);

    Series.renderSeriesSidebar(document.getElementById('seriesSidebar'), siteStructure, currentSeries);
    updateBreadcrumbs();
    renderProjectBanner();
    renderPeopleAndGalleries();
    setupSearch();
  } catch (error) {
    console.error('Error initializing page:', error);
    showError(`ページの読み込みに失敗しました: ${error.message}`);
  }
});

// ============ Rendering ============

function updateBreadcrumbs() {
  const breadcrumb = document.querySelector('.breadcrumbs-content');
  const seriesName = currentSeries || Series.getProjectSeries(currentProjectData);
  const projectLabel = currentProjectData.label || currentProject;

  Navigation.renderBreadcrumbs(breadcrumb, [
    { label: 'トップ', href: 'index.html' },
    { label: seriesName, href: Series.buildSeriesHref(seriesName), className: 'breadcrumb-series' },
    { label: projectLabel, current: true, className: 'breadcrumb-current', id: 'projectName' }
  ]);
}

function renderProjectBanner() {
  const bannerDiv = document.querySelector('.project-banner-large');
  if (!bannerDiv) {
    return;
  }

  bannerDiv.innerHTML = '';

  if (currentProjectData.banner) {
    const img = document.createElement('img');
    img.src = currentProjectData.banner;
    img.alt = currentProjectData.label || currentProject;
    img.onerror = () => {
      img.style.display = 'none';
      bannerDiv.innerHTML = `<div class="project-banner-placeholder">${currentProjectData.label || currentProject}</div>`;
    };
    bannerDiv.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'project-banner-placeholder';
    placeholder.textContent = currentProjectData.label || currentProject;
    bannerDiv.appendChild(placeholder);
  }
}

function renderPeopleAndGalleries() {
  const container = document.getElementById('peopleContainer');
  if (!container) {
    return;
  }

  container.innerHTML = '';
  hideNoResults();

  const people = extractPeople();
  if (people.length === 0) {
    renderProjectToc([]);
    showNoResults();
    return;
  }

  const tocEntries = [];

  people.forEach((person, index) => {
    const anchorId = buildPersonAnchorId(person, index);
    container.appendChild(createPeopleSection(person, anchorId));
    tocEntries.push({
      id: anchorId,
      label: person.label,
    });
  });

  renderProjectToc(tocEntries);
}

function extractPeople() {
  const people = [];

  for (const [key, value] of Object.entries(currentProjectData || {})) {
    if (key === 'label' || key === 'banner' || key === 'series') {
      continue;
    }

    if (!value || typeof value !== 'object' || !Array.isArray(value.galleries)) {
      continue;
    }

    people.push({
      key,
      label: value.label || key,
      galleries: value.galleries,
      extUrls: Search.getPersonExternalLinks(value),
    });
  }

  return people;
}

function createPeopleSection(person, anchorId) {
  const section = document.createElement('div');
  section.className = 'gallery-section';

  const heading = document.createElement('h2');
  heading.className = 'gallery-section-title';
  heading.id = anchorId;

  const link = document.createElement('a');
  link.href = '#';
  link.textContent = person.label;
  link.style.color = '#0066cc';
  link.addEventListener('click', (event) => {
    event.preventDefault();
    navigateToPerson(person.key);
  });

  heading.appendChild(link);
  section.appendChild(heading);

  if (Array.isArray(person.extUrls) && person.extUrls.length > 0) {
    section.appendChild(createExternalLinksBlock(person.extUrls));
  }

  const grid = document.createElement('div');
  grid.className = 'gallery-grid';

  person.galleries.forEach((gallery, index) => {
    grid.appendChild(createGalleryItem(gallery, index, person.key));
  });

  section.appendChild(grid);
  return section;
}

function createGalleryItem(gallery, index, personKey) {
  const link = document.createElement('a');
  link.className = 'gallery-item';
  link.href = `gallery.html?project=${encodeURIComponent(currentProject)}&person=${encodeURIComponent(personKey)}&gallery=${encodeURIComponent(gallery.path)}`;

  const thumbDiv = document.createElement('div');
  thumbDiv.className = 'gallery-thumbnail';

  if (gallery.thumbnail) {
    const img = document.createElement('img');
    img.src = gallery.thumbnail;
    img.alt = `Gallery ${index + 1}`;
    img.onerror = () => {
      img.style.display = 'none';
      thumbDiv.innerHTML = '<div class="gallery-thumbnail-placeholder">No image</div>';
    };
    thumbDiv.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'gallery-thumbnail-placeholder';
    placeholder.textContent = 'No image';
    thumbDiv.appendChild(placeholder);
  }

  link.appendChild(thumbDiv);
  link.appendChild(createGalleryMeta(gallery));

  const labelDiv = document.createElement('div');
  labelDiv.className = 'gallery-label';
  labelDiv.textContent = extractGalleryLabel(gallery.path);
  link.appendChild(labelDiv);

  return link;
}

function createGalleryMeta(gallery) {
  const { pictureCount, videoCount } = getGalleryMediaCounts(gallery);
  const meta = document.createElement('div');
  meta.className = 'gallery-meta';
  meta.innerHTML = `
    <span class="gallery-meta-item"><i class="fa-regular fa-images" aria-hidden="true"></i><span>picture:${pictureCount}</span></span>
    <span class="gallery-meta-item"><i class="fa-solid fa-film" aria-hidden="true"></i><span>video:${videoCount}</span></span>
  `;
  return meta;
}

function getGalleryMediaCounts(gallery) {
  const key = normalizeGalleryPath(gallery?.path || '');
  const map = window.galleryPagesMap || {};
  const entries = Array.isArray(map[key]) ? map[key] : [];

  if (entries.length === 0) {
    return {
      pictureCount: gallery?.thumbnail ? 1 : 0,
      videoCount: 0,
    };
  }

  return entries.reduce((counts, entry) => {
    const type = entry?.type || (entry?.video ? 'video' : 'image');
    if (type === 'video') {
      counts.videoCount += 1;
    } else {
      counts.pictureCount += 1;
    }
    return counts;
  }, { pictureCount: 0, videoCount: 0 });
}

function normalizeGalleryPath(path) {
  return String(path || '').replace(/\\/g, '/').replace(/^\/+/, '');
}

function extractGalleryLabel(path) {
  let parts = path.replace(/^photo\//, '').split('/');
  parts = parts.slice(1);
  parts = parts.slice(0, -1);
  return parts.join(' / ');
}

function createExternalLinksBlock(extUrls) {
  const block = document.createElement('div');
  block.className = 'external-links';

  for (const ext of extUrls) {
    const link = document.createElement('a');
    link.className = 'external-link';
    link.href = ext.url;
    link.textContent = `📄 ${ext.caption}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    block.appendChild(link);
  }

  return block;
}

function buildPersonAnchorId(person, index) {
  const base = String(person.key || person.label || `person-${index + 1}`)
    .toLowerCase()
    .replace(/[^a-z0-9\u3040-\u30ff\u4e00-\u9faf_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return `person-section-${base || index + 1}`;
}

function renderProjectToc(entries) {
  const toc = document.getElementById('projectToc');
  if (!toc) {
    return;
  }

  if (!entries || entries.length === 0) {
    toc.innerHTML = '';
    toc.hidden = true;
    return;
  }

  toc.hidden = false;
  toc.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'project-toc-title';
  title.textContent = '人物目次';
  toc.appendChild(title);

  const list = document.createElement('div');
  list.className = 'project-toc-list';

  entries.forEach(({ id, label }) => {
    const link = document.createElement('a');
    link.className = 'project-toc-link';
    link.href = `#${id}`;
    link.textContent = label;
    list.appendChild(link);
  });

  toc.appendChild(list);
}

// ============ Navigation ============

function navigateToPerson(personKey) {
  window.location.href = `person.html?project=${encodeURIComponent(currentProject)}&person=${encodeURIComponent(personKey)}`;
}

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) {
    return;
  }

  searchInput.addEventListener('input', (event) => {
    const query = event.target.value;
    if (query.trim().length === 0) {
      renderPeopleAndGalleries();
      return;
    }

    renderSearchResults(searchPeopleInProject(query));
  });

  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      searchInput.value = '';
      renderPeopleAndGalleries();
    }
  });
}

function searchPeopleInProject(query) {
  return extractPeople().filter((person) => Search.matchesPersonName(person.label, query));
}

function renderSearchResults(results) {
  const container = document.getElementById('peopleContainer');
  if (!container) {
    return;
  }

  container.innerHTML = '';
  if (results.length === 0) {
    renderProjectToc([]);
    showNoResults();
    return;
  }

  hideNoResults();
  const tocEntries = [];

  results.forEach((person, index) => {
    const anchorId = buildPersonAnchorId(person, index);
    container.appendChild(createPeopleSection(person, anchorId));
    tocEntries.push({
      id: anchorId,
      label: person.label,
    });
  });

  renderProjectToc(tocEntries);
}

// ============ Utilities ============

function showNoResults() {
  const noResults = document.getElementById('noResults');
  if (noResults) {
    noResults.classList.remove('hidden');
  }
}

function hideNoResults() {
  const noResults = document.getElementById('noResults');
  if (noResults) {
    noResults.classList.add('hidden');
  }
}

function showError(message) {
  const container = document.getElementById('peopleContainer');
  if (container) {
    container.innerHTML = `<div class="no-results">${message}</div>`;
  }
}
