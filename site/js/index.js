/**
 * Index Page Main Script
 * Handles project listing, series filtering, search, and navigation.
 */

let siteStructure = null;
let siteConfig = null;
let activeSeries = '';
let viewMode = 'cards';

const VIEW_MODES = {
  CARDS: 'cards',
  SIMPLE_LIST: 'simple-list',
};

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }

    siteStructure = window.siteStructure;
    siteConfig = window.siteConfig || {};

    const params = new URLSearchParams(window.location.search);
    activeSeries = Series.getRequestedSeries(siteStructure, siteConfig, params.get('series'));

    const sidebar = document.getElementById('seriesSidebar');
    Series.renderSeriesSidebar(sidebar, siteStructure, activeSeries);

    setupViewModeControls();
    updateBreadcrumbs();
    renderProjectList();
    setupSearch();
    handlePersonParam(params);
  } catch (error) {
    console.error('Error initializing page:', error);
    showError(`サイトの読み込みに失敗しました: ${error.message}`);
  }
});

// ============ Rendering ============

function getFilteredStructure() {
  return Series.filterStructureBySeries(siteStructure, activeSeries);
}

function renderProjectList() {
  const container = document.getElementById('projectsContainer');
  if (!container) {
    return;
  }

  container.innerHTML = '';
  container.classList.remove('project-grid', 'project-simple-list');
  if (viewMode === VIEW_MODES.SIMPLE_LIST) {
    container.classList.add('project-simple-list');
  } else {
    container.classList.add('project-grid');
  }

  hideNoResults();

  const filteredStructure = getFilteredStructure();
  const projectEntries = Object.entries(filteredStructure);
  if (projectEntries.length === 0) {
    showNoResults();
    return;
  }

  for (const [projectKey, project] of projectEntries) {
    const people = Series.extractPeople(project);
    if (viewMode === VIEW_MODES.SIMPLE_LIST) {
      container.appendChild(createSimpleProjectItem(projectKey, project.label || projectKey, people));
    } else {
      container.appendChild(createProjectBlock(
        projectKey,
        project.label || projectKey,
        project.banner || '',
        people
      ));
    }
  }
}

function createProjectBlock(projectKey, projectLabel, bannerPath, people) {
  const block = document.createElement('div');
  block.className = 'project-block';

  const bannerDiv = document.createElement('div');
  bannerDiv.className = 'project-banner';
  if (bannerPath) {
    const img = document.createElement('img');
    img.src = bannerPath;
    img.alt = projectLabel;
    img.onerror = () => {
      img.style.display = 'none';
      bannerDiv.innerHTML = `<div class="project-banner-placeholder">${projectLabel}</div>`;
    };
    bannerDiv.appendChild(img);
  } else {
    const placeholder = document.createElement('div');
    placeholder.className = 'project-banner-placeholder';
    placeholder.textContent = projectLabel;
    bannerDiv.appendChild(placeholder);
  }

  bannerDiv.style.cursor = 'pointer';
  bannerDiv.addEventListener('click', () => {
    navigateToProject(projectKey);
  });
  block.appendChild(bannerDiv);

  const peopleDiv = document.createElement('div');
  peopleDiv.className = 'project-people';

  for (const person of people) {
    const link = document.createElement('a');
    link.className = 'person-link';
    link.textContent = person.label;
    link.href = '#';
    link.addEventListener('click', (event) => {
      event.preventDefault();
      navigateToPerson(projectKey, person.key);
    });
    peopleDiv.appendChild(link);
  }

  block.appendChild(peopleDiv);
  return block;
}

function createSimpleProjectItem(projectKey, projectLabel, people) {
  const item = document.createElement('section');
  item.className = 'project-simple-item';

  const title = document.createElement('h2');
  title.className = 'project-simple-title';
  title.textContent = projectLabel;
  title.addEventListener('click', () => {
    navigateToProject(projectKey);
  });
  item.appendChild(title);

  const peopleRow = document.createElement('div');
  peopleRow.className = 'project-simple-people';

  for (const person of people) {
    const link = document.createElement('a');
    link.className = 'person-link';
    link.textContent = person.label;
    link.href = '#';
    link.addEventListener('click', (event) => {
      event.preventDefault();
      navigateToPerson(projectKey, person.key);
    });
    peopleRow.appendChild(link);
  }

  item.appendChild(peopleRow);
  return item;
}

function setupViewModeControls() {
  const controls = document.getElementById('viewModeControls');
  if (!controls) {
    return;
  }

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
    if (viewMode === mode) {
      return;
    }
    viewMode = mode;
    updateViewModeControls();

    const searchInput = document.getElementById('searchInput');
    if (searchInput && searchInput.value.trim().length > 0) {
      return;
    }
    renderProjectList();
  });

  return button;
}

function updateViewModeControls() {
  const controls = document.getElementById('viewModeControls');
  if (!controls) {
    return;
  }

  const buttons = controls.querySelectorAll('.view-mode-button');
  buttons.forEach((button) => {
    const active = button.dataset.mode === viewMode;
    button.classList.toggle('is-active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

function renderSearchResults(seriesGroups) {
  const resultsContainer = document.getElementById('searchResultsContent');
  if (!resultsContainer) {
    return;
  }

  resultsContainer.innerHTML = '';
  if (seriesGroups.length === 0) {
    showNoResults();
    return;
  }

  hideNoResults();

  for (const { series, projects } of seriesGroups) {
    const seriesSection = document.createElement('div');
    seriesSection.className = 'search-series-section';

    const seriesHeading = document.createElement('h2');
    seriesHeading.className = 'search-series-heading';
    seriesHeading.textContent = series;
    seriesSection.appendChild(seriesHeading);

    for (const result of projects) {
      const projectBlock = document.createElement('div');
      projectBlock.className = 'search-project-block';

      const projectLabel = document.createElement('div');
      projectLabel.className = 'search-project-label';
      const projectLink = document.createElement('a');
      projectLink.href = `project.html?project=${encodeURIComponent(result.projectKey)}`;
      projectLink.textContent = result.projectLabel;
      projectLabel.appendChild(projectLink);
      const personSpan = document.createElement('span');
      personSpan.textContent = ` - ${result.personLabel}`;
      projectLabel.appendChild(personSpan);
      projectBlock.appendChild(projectLabel);

      if (Array.isArray(result.extUrls) && result.extUrls.length > 0) {
        projectBlock.appendChild(createExternalLinksBlock(result.extUrls));
      }

      const grid = document.createElement('div');
      grid.className = 'gallery-grid';
      for (const gallery of result.galleries) {
        grid.appendChild(createGalleryItem(gallery, result.projectKey, result.personKey));
      }
      projectBlock.appendChild(grid);
      seriesSection.appendChild(projectBlock);
    }

    resultsContainer.appendChild(seriesSection);
  }
}

function createGalleryItem(gallery, projectKey, personKey) {
  const link = document.createElement('a');
  link.className = 'gallery-item';
  link.href = `gallery.html?project=${encodeURIComponent(projectKey)}&person=${encodeURIComponent(personKey)}&gallery=${encodeURIComponent(gallery.path)}`;

  const thumbDiv = document.createElement('div');
  thumbDiv.className = 'gallery-thumbnail';

  if (gallery.thumbnail) {
    const img = document.createElement('img');
    img.src = gallery.thumbnail;
    img.alt = 'Gallery';
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

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) {
    return;
  }

  searchInput.addEventListener('input', (event) => {
    const query = event.target.value;
    const projectsContainer = document.getElementById('projectsContainer');
    const searchResults = document.getElementById('searchResults');

    if (query.trim().length === 0) {
      projectsContainer.classList.remove('hidden');
      searchResults.classList.add('hidden');
      hideNoResults();
      return;
    }

    const results = Search.searchPeopleGroupedBySeries(siteStructure, query);
    projectsContainer.classList.add('hidden');
    searchResults.classList.remove('hidden');
    renderSearchResults(results);
  });

  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      searchInput.value = '';
      searchInput.dispatchEvent(new Event('input'));
    }
  });
}

// ============ URL Parameter Handling ============

function updateBreadcrumbs(personParam = '') {
  const breadcrumb = document.getElementById('breadcrumbTrail');
  if (!breadcrumb) {
    return;
  }

  if (personParam) {
    Navigation.renderBreadcrumbs(breadcrumb, [
      { label: 'トップ', href: 'index.html' },
      { label: personParam, current: true, className: 'breadcrumb-current' }
    ]);
    return;
  }

  if (activeSeries) {
    Navigation.renderBreadcrumbs(breadcrumb, [
      { label: 'トップ', href: 'index.html' },
      { label: activeSeries, current: true, className: 'breadcrumb-current' }
    ]);
    return;
  }

  Navigation.renderBreadcrumbs(breadcrumb, [
    { label: 'トップ', current: true, className: 'breadcrumb-current' }
  ]);
}

function handlePersonParam(params) {
  const personParam = params.get('person');
  if (!personParam) {
    return;
  }

  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.value = personParam;
  }

  const results = Search.searchPeopleGroupedBySeries(siteStructure, personParam, true);
  const projectsContainer = document.getElementById('projectsContainer');
  const searchResults = document.getElementById('searchResults');
  if (projectsContainer) {
    projectsContainer.classList.add('hidden');
  }
  if (searchResults) {
    searchResults.classList.remove('hidden');
  }
  renderSearchResults(results);

  updateBreadcrumbs(personParam);
  document.title = `${personParam} - Photo Gallery`;
}

// ============ Navigation ============

function navigateToProject(projectKey) {
  window.location.href = `project.html?project=${encodeURIComponent(projectKey)}`;
}

function navigateToPerson(projectKey, personKey) {
  window.location.href = `person.html?project=${encodeURIComponent(projectKey)}&person=${encodeURIComponent(personKey)}`;
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
  const container = document.getElementById('projectsContainer');
  if (container) {
    container.innerHTML = `<div class="no-results">${message}</div>`;
  }
}
