/**
 * Search Utility Module
 * Provides search functionality for people and galleries
 */

const Search = (() => {
  const PROJECT_META_KEYS = new Set(['label', 'banner', 'series']);

  function normalizeExternalUrl(rawUrl) {
    if (typeof rawUrl !== 'string') {
      return '';
    }

    const url = rawUrl.trim();
    if (!url) {
      return '';
    }

    // Keep absolute URLs, anchors, and root-absolute paths unchanged.
    if (/^(https?:|file:|mailto:|#|\/)/i.test(url)) {
      return url;
    }

    if (url.startsWith('contents/')) {
      return url;
    }

    return `contents/${url.replace(/^\.\//, '')}`;
  }

  function getPersonExternalLinks(person) {
    if (!person || !Array.isArray(person.exturl)) {
      return [];
    }

    const links = [];
    for (const item of person.exturl) {
      if (!item || typeof item !== 'object') {
        continue;
      }

      const caption = typeof item.caption === 'string' ? item.caption.trim() : '';
      const href = normalizeExternalUrl(item.url);
      if (!caption || !href) {
        continue;
      }

      links.push({ caption, url: href });
    }

    return links;
  }

  function matchesPersonName(personName, query, exactMatch = false) {
    const normalizedQuery = String(query || '').trim().toLowerCase();
    if (!normalizedQuery) {
      return false;
    }

    const normalizedPersonName = String(personName || '').trim().toLowerCase();
    return exactMatch
      ? normalizedPersonName === normalizedQuery
      : normalizedPersonName.includes(normalizedQuery);
  }

  /**
   * Search people by partial match
   * @param {Object} structure - The structure.json data
   * @param {string} query - Search query (person name partial text)
   * @returns {Array} Array of matching results with format { project, person, galleries }
   */
  function searchPeople(structure, query) {
    if (!query || query.trim().length === 0) {
      return [];
    }

    const results = [];

    for (const [projectKey, project] of Object.entries(structure || {})) {
      for (const [personKey, person] of Object.entries(project || {})) {
        if (PROJECT_META_KEYS.has(personKey)) {
          continue;
        }

        if (typeof person !== 'object' || !person.galleries) {
          continue;
        }

        const personName = person.label || personKey;
        if (matchesPersonName(personName, query)) {
          results.push({
            project: projectKey,
            projectLabel: project.label,
            projectBanner: project.banner,
            person: personKey,
            personLabel: personName,
            galleries: person.galleries,
            extUrls: getPersonExternalLinks(person),
          });
        }
      }
    }

    return results;
  }

  /**
   * Get all people and their galleries for display
   * @param {Object} structure - The structure.json data
   * @returns {Array} Array of all people with their galleries
   */
  function getAllPeople(structure) {
    const allPeople = [];

    for (const [projectKey, project] of Object.entries(structure || {})) {
      for (const [personKey, person] of Object.entries(project)) {
        if (personKey === 'label' || personKey === 'banner' || personKey === 'galleries') {
          continue;
        }

        if (typeof person === 'object' && person.galleries) {
          allPeople.push({
            project: projectKey,
            projectLabel: project.label,
            projectBanner: project.banner,
            person: personKey,
            personLabel: person.label || personKey,
            galleries: person.galleries,
            extUrls: getPersonExternalLinks(person),
          });
        }
      }
    }

    return allPeople;
  }

  /**
   * Search people by partial match across all series, grouped by series
   * @param {Object} structure - The full structure.json data (all series)
   * @param {string} query - Search query (person name partial text or exact name)
   * @param {boolean} exactMatch - If true, match exact name instead of partial text
   * @returns {Array} Array of { series, projects: [{ projectKey, projectLabel, projectBanner, personKey, personLabel, galleries }] }
   */
  function searchPeopleGroupedBySeries(structure, query, exactMatch) {
    if (!query || query.trim().length === 0) {
      return [];
    }

    const seriesMap = new Map();

    for (const [projectKey, project] of Object.entries(structure || {})) {
      const seriesName = (typeof project.series === 'string' && project.series.trim())
        ? project.series.trim()
        : '未分類';

      for (const [personKey, person] of Object.entries(project)) {
        if (PROJECT_META_KEYS.has(personKey)) {
          continue;
        }
        if (typeof person !== 'object' || !Array.isArray(person.galleries)) {
          continue;
        }

        const personName = person.label || personKey;
        const match = matchesPersonName(personName, query, exactMatch);

        if (match) {
          if (!seriesMap.has(seriesName)) {
            seriesMap.set(seriesName, []);
          }
          seriesMap.get(seriesName).push({
            projectKey,
            projectLabel: project.label || projectKey,
            projectBanner: project.banner || '',
            personKey,
            personLabel: personName,
            galleries: person.galleries,
            extUrls: getPersonExternalLinks(person),
          });
        }
      }
    }

    return Array.from(seriesMap.entries()).map(([series, projects]) => ({ series, projects }));
  }

  return {
    getPersonExternalLinks,
    normalizeExternalUrl,
    matchesPersonName,
    searchPeople,
    getAllPeople,
    searchPeopleGroupedBySeries,
  };
})();

if (typeof window !== 'undefined') {
  window.Search = Search;
}
