/**
 * Structure utilities for genres/series navigation.
 * Shared across all pages.
 */

const Series = (() => {
  const GENRE_META_KEYS = new Set(['name', 'path', 'note', 'labels', 'class', 'classname', 'browse', 'searchkey', 'searchkeyname', 'entries']);
  const UNCATEGORIZED_SERIES = '未分類';

  // ---- Data access ----

  function getGenres(structure) {
    return (structure && typeof structure.genres === 'object') ? structure.genres : {};
  }

  function getGenreName(structure, genreKey) {
    const genres = getGenres(structure);
    return (genres[genreKey] && genres[genreKey].name) || genreKey;
  }

  function getGenreEntriesMap(genre) {
    if (!genre || typeof genre !== 'object') return {};

    if (genre.entries && typeof genre.entries === 'object' && !Array.isArray(genre.entries)) {
      return genre.entries;
    }

    return genre;
  }

  function getSeriesEntries(structure, genreKey) {
    const genres = getGenres(structure);
    const genre = genres[genreKey];
    if (!genre || typeof genre !== 'object') return {};

    const source = getGenreEntriesMap(genre);
    const entries = {};
    for (const [key, value] of Object.entries(source)) {
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
      const source = getGenreEntriesMap(genreData);
      for (const [seriesKey, seriesData] of Object.entries(source)) {
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

    const entries = getGenreEntriesMap(genre);
    return entries[seriesKey] || null;
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

  function getGenreClassConfig(structure, genreKey) {
    const genres = getGenres(structure);
    const genre = genres[genreKey];
    if (!genre || typeof genre !== 'object') {
      return {
        classKeys: [],
        classNames: [],
        browse: {
          leafType: 'series',
          contentGroupBy: 'flat',
          unknownLabel: UNCATEGORIZED_SERIES,
        },
      };
    }

    const classKeys = Array.isArray(genre.class)
      ? genre.class.filter((key) => typeof key === 'string' && key.trim().length > 0)
      : [];

    const classNamesRaw = Array.isArray(genre.classname) ? genre.classname : [];
    const classNames = classKeys.map((key, index) => {
      const name = classNamesRaw[index];
      return (typeof name === 'string' && name.trim().length > 0) ? name.trim() : key;
    });

    const browseRaw = (genre.browse && typeof genre.browse === 'object') ? genre.browse : {};
    const leafType = browseRaw.leafType === 'content' ? 'content' : 'series';
    const allowedGroupBy = new Set(['flat', 'none', 'path-depth-1', 'path-depth-2']);
    const contentGroupBy = allowedGroupBy.has(browseRaw.contentGroupBy)
      ? browseRaw.contentGroupBy
      : 'flat';
    const unknownLabel = (typeof browseRaw.unknownLabel === 'string' && browseRaw.unknownLabel.trim().length > 0)
      ? browseRaw.unknownLabel.trim()
      : UNCATEGORIZED_SERIES;

    return {
      classKeys,
      classNames,
      browse: {
        leafType,
        contentGroupBy,
        unknownLabel,
      },
    };
  }

  function getGenreSearchConfig(structure, genreKey) {
    const genres = getGenres(structure);
    const genre = genres[genreKey];
    if (!genre || typeof genre !== 'object') {
      return {
        keys: [],
        names: [],
      };
    }

    const keys = Array.isArray(genre.searchkey)
      ? genre.searchkey
        .filter((key) => typeof key === 'string')
        .map((key) => key.trim())
        .filter(Boolean)
      : [];

    const namesRaw = Array.isArray(genre.searchkeyname) ? genre.searchkeyname : [];
    const names = keys.map((key, index) => {
      const name = namesRaw[index];
      return (typeof name === 'string' && name.trim().length > 0) ? name.trim() : key;
    });

    return { keys, names };
  }

  function getEntryClassValues(entryData, classKey) {
    if (!entryData || !classKey) return [];
    const value = entryData[classKey];

    if (typeof value === 'string') {
      const trimmed = value.trim();
      return trimmed ? [trimmed] : [];
    }

    if (Array.isArray(value)) {
      return value
        .filter((item) => typeof item === 'string')
        .map((item) => item.trim())
        .filter(Boolean);
    }

    return [];
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

  function buildGenreClassBrowseHref(genreKey, classValue) {
    let href = 'index.html?genre=' + encodeURIComponent(genreKey) + '&classBrowse=1';
    if (typeof classValue === 'string' && classValue.trim().length > 0) {
      href += '&classValue=' + encodeURIComponent(classValue.trim());
    }
    return href;
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

    const classBrowseList = document.createElement('div');
    classBrowseList.className = 'sidebar-list';

    const url = new URL(window.location.href);
    const currentGenre = decodeURIComponent(url.searchParams.get('genre') || '');
    const isClassBrowse = url.searchParams.get('classBrowse') === '1';

    for (const [genreKey, genreData] of Object.entries(getGenres(structure))) {
      if (!genreData || typeof genreData !== 'object') continue;
      const { classKeys, classNames } = getGenreClassConfig(structure, genreKey);
      if (classKeys.length === 0) continue;

      const primaryClassName = classNames[0] || classKeys[0];
      const link = document.createElement('a');
      link.className = 'sidebar-link';
      link.href = buildGenreClassBrowseHref(genreKey);
      link.textContent = (genreData.name || genreKey) + '：' + primaryClassName + '一覧';

      if (window.location.pathname.endsWith('index.html')
        && isClassBrowse
        && currentGenre === genreKey) {
        link.classList.add('is-active');
        link.setAttribute('aria-current', 'page');
      }

      classBrowseList.appendChild(link);
    }

    if (classBrowseList.childElementCount > 0) {
      container.appendChild(classBrowseList);

      const secondDivider = document.createElement('hr');
      secondDivider.className = 'sidebar-divider';
      container.appendChild(secondDivider);
    }

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
    getGenreClassConfig,
    getGenreSearchConfig,
    getEntryClassValues,
    getPersonList,
    buildGenreHref,
    buildSeriesHref,
    buildGenreClassBrowseHref,
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
