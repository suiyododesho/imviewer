/**
 * Structure utilities for genres/series navigation.
 * Shared across all pages.
 */

const Series = (() => {
  const GENRE_META_KEYS = new Set(['name', 'path', 'note', 'labels']);
  const UNCATEGORIZED_SERIES = '未分類';

  // ---- Data access ----

  function getGenres(structure) {
    return (structure && typeof structure.genres === 'object') ? structure.genres : {};
  }

  function getGenreName(structure, genreKey) {
    const genres = getGenres(structure);
    return (genres[genreKey] && genres[genreKey].name) || genreKey;
  }

  function getSeriesEntries(structure, genreKey) {
    const genres = getGenres(structure);
    const genre = genres[genreKey];
    if (!genre || typeof genre !== 'object') return {};
    const entries = {};
    for (const [key, value] of Object.entries(genre)) {
      if (GENRE_META_KEYS.has(key)) continue;
      if (!value || typeof value !== 'object') continue;
      entries[key] = value;
    }
    return entries;
  }

  function getAllSeriesEntries(structure) {
    const result = [];
    for (const [genreKey, genreData] of Object.entries(getGenres(structure))) {
      if (!genreData || typeof genreData !== 'object') continue;
      for (const [seriesKey, seriesData] of Object.entries(genreData)) {
        if (GENRE_META_KEYS.has(seriesKey)) continue;
        if (!seriesData || typeof seriesData !== 'object') continue;
        result.push({ genreKey, seriesKey, data: seriesData });
      }
    }
    return result;
  }

  function getEntryByKey(structure, genreKey, seriesKey) {
    const genres = getGenres(structure);
    const genre = genres[genreKey];
    if (!genre) return null;
    return genre[seriesKey] || null;
  }

  function getSeriesName(entryData) {
    const val = (entryData && typeof entryData.series === 'string') ? entryData.series.trim() : '';
    return val || UNCATEGORIZED_SERIES;
  }

  function getFirstContentCover(entryData) {
    const contents = entryData && entryData.contents;
    if (!Array.isArray(contents) || contents.length === 0) return '';
    return contents[0].cover || '';
  }

  function getContentCount(entryData) {
    return (entryData && Array.isArray(entryData.contents)) ? entryData.contents.length : 0;
  }

  function getMainPerson(entryData) {
    return (entryData && typeof entryData['main-person'] === 'string')
      ? entryData['main-person'].trim()
      : '';
  }

  function getPersonList(entryData) {
    const main = getMainPerson(entryData);
    const extras = (entryData && Array.isArray(entryData.persons))
      ? entryData.persons.filter(Boolean)
      : [];
    if (!main) return extras;
    return [main, ...extras.filter(p => p !== main)];
  }

  // ---- URL building ----

  function buildGenreHref(genreKey) {
    if (!genreKey) return 'index.html';
    return 'index.html?genre=' + encodeURIComponent(genreKey);
  }

  function buildSeriesHref(genreKey, seriesKey) {
    return 'project.html?genre=' + encodeURIComponent(genreKey) + '&series=' + encodeURIComponent(seriesKey);
  }

  function buildGalleryHref(genreKey, seriesKey, contentPath) {
    return 'gallery.html?genre=' + encodeURIComponent(genreKey)
      + '&series=' + encodeURIComponent(seriesKey)
      + '&content=' + encodeURIComponent(contentPath);
  }

  // ---- Genre sidebar ----

  function renderGenreSidebar(container, structure, activeGenre) {
    if (!container) return;
    container.innerHTML = '';

    const title = document.createElement('h2');
    title.className = 'sidebar-title';
    title.textContent = 'ジャンル一覧';
    container.appendChild(title);

    const list = document.createElement('div');
    list.className = 'sidebar-list';

    for (const [genreKey, genreData] of Object.entries(getGenres(structure))) {
      if (!genreData || typeof genreData !== 'object') continue;
      const link = document.createElement('a');
      link.className = 'sidebar-link';
      if (genreKey === activeGenre) {
        link.classList.add('is-active');
        link.setAttribute('aria-current', 'page');
      }
      link.href = buildGenreHref(genreKey);
      link.textContent = genreData.name || genreKey;
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
    if (window.location.pathname.endsWith('persons.html')) {
      personsLink.classList.add('is-active');
      personsLink.setAttribute('aria-current', 'page');
    }
    container.appendChild(personsLink);
  }

  // Alias for legacy callers
  function renderSeriesSidebar(container, structure, activeGenre) {
    renderGenreSidebar(container, structure, activeGenre);
  }

  // ---- Legacy shims ----

  function getProjectSeries(entryData) {
    if (!entryData) return UNCATEGORIZED_SERIES;
    return (typeof entryData.series === 'string' && entryData.series.trim())
      ? entryData.series.trim()
      : (entryData.name || UNCATEGORIZED_SERIES);
  }

  function getAllSeries() { return []; }

  function buildSeriesHrefLegacy(series) {
    return 'index.html?genre=' + encodeURIComponent(series);
  }

  return {
    UNCATEGORIZED_SERIES,
    getGenres,
    getGenreName,
    getSeriesEntries,
    getAllSeriesEntries,
    getEntryByKey,
    getSeriesName,
    getFirstContentCover,
    getContentCount,
    getMainPerson,
    getPersonList,
    buildGenreHref,
    buildSeriesHref,
    buildGalleryHref,
    renderGenreSidebar,
    renderSeriesSidebar,
    getProjectSeries,
    getAllSeries,
  };
})();

if (typeof window !== 'undefined') {
  window.Series = Series;
}
