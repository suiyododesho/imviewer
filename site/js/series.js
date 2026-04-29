/**
 * Series utilities and shared sidebar rendering.
 */

const Series = (() => {
  const META_KEYS = new Set(['label', 'banner', 'series']);
  const UNCATEGORIZED_SERIES = '未分類';

  function getProjectSeries(projectData) {
    if (!projectData || typeof projectData !== 'object') {
      return UNCATEGORIZED_SERIES;
    }

    const value = typeof projectData.series === 'string' ? projectData.series.trim() : '';
    return value || UNCATEGORIZED_SERIES;
  }

  function getAllSeries(structure) {
    const seen = new Set();
    const seriesList = [];

    for (const projectData of Object.values(structure || {})) {
      const series = getProjectSeries(projectData);
      if (!seen.has(series)) {
        seen.add(series);
        seriesList.push(series);
      }
    }

    return seriesList.sort((a, b) => {
      if (a === UNCATEGORIZED_SERIES) return 1;
      if (b === UNCATEGORIZED_SERIES) return -1;
      return 0;
    });
  }

  function getDefaultSeries(structure, config) {
    const seriesList = getAllSeries(structure);
    if (seriesList.length === 0) {
      return '';
    }

    const configured = typeof config?.defaultSeries === 'string' ? config.defaultSeries.trim() : '';
    if (configured && seriesList.includes(configured)) {
      return configured;
    }

    return seriesList[0];
  }

  function getRequestedSeries(structure, config, requestedSeries) {
    const seriesList = getAllSeries(structure);
    if (seriesList.length === 0) {
      return '';
    }

    const requested = typeof requestedSeries === 'string' ? requestedSeries.trim() : '';
    if (requested && seriesList.includes(requested)) {
      return requested;
    }

    return getDefaultSeries(structure, config);
  }

  function filterStructureBySeries(structure, series) {
    if (!series) {
      return structure || {};
    }

    const filtered = {};
    for (const [projectKey, projectData] of Object.entries(structure || {})) {
      if (getProjectSeries(projectData) === series) {
        filtered[projectKey] = projectData;
      }
    }
    return filtered;
  }

  function buildSeriesHref(series) {
    return `index.html?series=${encodeURIComponent(series)}`;
  }

  function renderSeriesSidebar(container, structure, activeSeries) {
    if (!container) {
      return;
    }

    const seriesList = getAllSeries(structure);
    container.innerHTML = '';

    const title = document.createElement('h2');
    title.className = 'sidebar-title';
    title.textContent = 'シリーズ一覧';
    container.appendChild(title);

    const list = document.createElement('div');
    list.className = 'sidebar-list';

    for (const series of seriesList) {
      const link = document.createElement('a');
      link.className = 'sidebar-link';
      if (series === activeSeries) {
        link.classList.add('is-active');
        link.setAttribute('aria-current', 'page');
      }
      link.href = buildSeriesHref(series);
      link.textContent = series;
      list.appendChild(link);
    }

    container.appendChild(list);

    const divider = document.createElement('hr');
    divider.className = 'sidebar-divider';
    container.appendChild(divider);

    const personsLink = document.createElement('a');
    personsLink.className = 'sidebar-link';
    personsLink.href = 'persons.html';
    personsLink.textContent = '全人物一覧';
    const currentPath = window.location.pathname;
    if (currentPath.endsWith('persons.html') || currentPath.endsWith('/persons')) {
      personsLink.classList.add('is-active');
      personsLink.setAttribute('aria-current', 'page');
    }
    container.appendChild(personsLink);
  }

  function extractPeople(projectData) {
    const people = [];

    for (const [key, value] of Object.entries(projectData || {})) {
      if (META_KEYS.has(key)) {
        continue;
      }
      if (value && typeof value === 'object' && Array.isArray(value.galleries)) {
        people.push({
          key,
          label: value.label || key,
          galleries: value.galleries,
        });
      }
    }

    return people;
  }

  return {
    UNCATEGORIZED_SERIES,
    buildSeriesHref,
    extractPeople,
    filterStructureBySeries,
    getAllSeries,
    getDefaultSeries,
    getProjectSeries,
    getRequestedSeries,
    renderSeriesSidebar,
  };
})();

if (typeof window !== 'undefined') {
  window.Series = Series;
}
