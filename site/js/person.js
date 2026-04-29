/**
 * Person Page Main Script
 * Handles display of galleries for a specific person.
 */

let siteStructure = null;
let currentProject = null;
let currentPerson = null;
let currentPersonData = null;

// ============ Initialization ============

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }

    siteStructure = window.siteStructure;

    const params = new URLSearchParams(window.location.search);
    currentProject = decodeURIComponent(params.get('project') || '');
    currentPerson = decodeURIComponent(params.get('person') || '');

    if (!currentProject || !currentPerson) {
      showError('人物情報がありません');
      return;
    }

    if (!siteStructure[currentProject]) {
      showError('企画が見つかりません');
      return;
    }

    const projectData = siteStructure[currentProject];
    currentPersonData = projectData[currentPerson];
    if (!currentPersonData || !Array.isArray(currentPersonData.galleries)) {
      showError('人物またはギャラリーが見つかりません');
      return;
    }

    Series.renderSeriesSidebar(
      document.getElementById('seriesSidebar'),
      siteStructure,
      Series.getProjectSeries(projectData)
    );

    updateBreadcrumbs(projectData);
    renderGalleries();
    setupNavigation();
    setupSearch();
  } catch (error) {
    console.error('Error initializing page:', error);
    showError(`ページの読み込みに失敗しました: ${error.message}`);
  }
});

// ============ Rendering ============

function updateBreadcrumbs(projectData) {
  const breadcrumb = document.querySelector('.breadcrumbs-content');
  const seriesName = Series.getProjectSeries(projectData);
  const projectLabel = projectData.label || currentProject;
  const personLabel = currentPersonData.label || currentPerson;

  Navigation.renderBreadcrumbs(breadcrumb, [
    { label: 'トップ', href: 'index.html' },
    { label: seriesName, href: Series.buildSeriesHref(seriesName), className: 'breadcrumb-series', id: 'seriesLink' },
    { label: projectLabel, href: `project.html?project=${encodeURIComponent(currentProject)}`, className: 'breadcrumb-project', id: 'projectLink' },
    { label: personLabel, current: true, className: 'breadcrumb-current', id: 'personName' }
  ]);
}

function renderGalleries() {
  const container = document.getElementById('galleryContainer');
  if (!container) {
    return;
  }

  renderExternalLinks();
  container.innerHTML = '';
  hideNoResults();

  const galleries = currentPersonData.galleries;
  if (galleries.length === 0) {
    showNoResults();
    return;
  }

  galleries.forEach((gallery, index) => {
    container.appendChild(createGalleryItem(gallery, index));
  });

  updateNavigationInfo();
}

function renderExternalLinks() {
  const linksContainer = document.getElementById('personExternalLinks');
  if (!linksContainer) {
    return;
  }

  linksContainer.innerHTML = '';
  const links = Search.getPersonExternalLinks(currentPersonData);
  if (links.length === 0) {
    linksContainer.classList.add('hidden');
    return;
  }

  linksContainer.classList.remove('hidden');
  for (const ext of links) {
    const link = document.createElement('a');
    link.className = 'external-link';
    link.href = ext.url;
    link.textContent = `📄 ${ext.caption}`;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    linksContainer.appendChild(link);
  }
}

function createGalleryItem(gallery, index) {
  const link = document.createElement('a');
  link.className = 'gallery-item';
  link.href = `gallery.html?project=${encodeURIComponent(currentProject)}&person=${encodeURIComponent(currentPerson)}&gallery=${encodeURIComponent(gallery.path)}`;

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

function updateNavigationInfo() {
  const info = document.getElementById('navInfo');
  if (info) {
    info.textContent = `${currentPersonData.galleries.length} ギャラリー`;
  }
}

// ============ Navigation ============

function setupNavigation() {
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');

  if (prevButton) {
    prevButton.addEventListener('click', navigatePrevPerson);
  }

  if (nextButton) {
    nextButton.addEventListener('click', navigateNextPerson);
  }

  updateNavigationButtons();
}

function getProjectPeople() {
  return Series.extractPeople(siteStructure[currentProject]);
}

function navigatePrevPerson() {
  const people = getProjectPeople();
  const curIndex = people.findIndex((person) => person.key === currentPerson);
  if (curIndex > 0) {
    const prevPerson = people[curIndex - 1];
    window.location.href = `person.html?project=${encodeURIComponent(currentProject)}&person=${encodeURIComponent(prevPerson.key)}`;
  }
}

function navigateNextPerson() {
  const people = getProjectPeople();
  const curIndex = people.findIndex((person) => person.key === currentPerson);
  if (curIndex >= 0 && curIndex < people.length - 1) {
    const nextPerson = people[curIndex + 1];
    window.location.href = `person.html?project=${encodeURIComponent(currentProject)}&person=${encodeURIComponent(nextPerson.key)}`;
  }
}

function updateNavigationButtons() {
  const people = getProjectPeople();
  const curIndex = people.findIndex((person) => person.key === currentPerson);
  const prevButton = document.getElementById('prevButton');
  const nextButton = document.getElementById('nextButton');

  if (prevButton) {
    prevButton.disabled = curIndex <= 0;
  }

  if (nextButton) {
    nextButton.disabled = curIndex === -1 || curIndex >= people.length - 1;
  }
}

// ============ Search ============

function setupSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) {
    return;
  }

  searchInput.addEventListener('input', (event) => {
    const query = event.target.value;
    if (query.trim().length > 0) {
      window.location.href = `index.html?series=${encodeURIComponent(Series.getProjectSeries(siteStructure[currentProject]))}`;
    }
  });

  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      searchInput.value = '';
    }
  });
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
  const container = document.getElementById('galleryContainer');
  if (container) {
    container.innerHTML = `<div class="no-results" style="grid-column: 1/-1;">${message}</div>`;
  }
}
