/**
 * Search Utility Module
 * Provides search functionality for persons and series entries.
 */

const Search = (() => {

  function normalizeExternalUrl(rawUrl) {
    if (typeof rawUrl !== 'string') return '';
    const url = rawUrl.trim();
    if (!url) return '';
    if (/^(https?:|file:|mailto:|#|\/)/i.test(url)) return url;
    if (url.startsWith('contents/')) return url;
    return 'contents/' + url.replace(/^\.\//, '');
  }

  function getEntryExternalLinks(entryData) {
    if (!entryData || !Array.isArray(entryData.exturl)) return [];
    const links = [];
    for (const item of entryData.exturl) {
      if (!item || typeof item !== 'object') continue;
      const caption = typeof item.caption === 'string' ? item.caption.trim() : '';
      const href = normalizeExternalUrl(item.url);
      if (!href) continue;
      links.push({ caption: caption || href, url: href });
    }
    return links;
  }

  // Legacy alias
  function getPersonExternalLinks(entryData) {
    return getEntryExternalLinks(entryData);
  }

  function matchesPersonName(name, query, exactMatch) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return false;
    const n = String(name || '').trim().toLowerCase();
    return exactMatch ? n === q : n.includes(q);
  }

  /**
   * Search series entries where main-person or persons[] match query.
   * Returns results grouped by genre.
   * @param {Object} structure - window.siteStructure
   * @param {string} query
   * @param {boolean} [exactMatch]
   * @returns {Array<{genreName, genreKey, entries: Array}>}
   */
  function searchEntriesGroupedByGenre(structure, query, exactMatch) {
    if (!query || !query.trim()) return [];

    const genreMap = new Map();

    for (const { genreKey, seriesKey, data } of Series.getAllSeriesEntries(structure)) {
      const persons = Series.getPersonList(data);
      const matchedPerson = persons.find(p => matchesPersonName(p, query, exactMatch));
      if (!matchedPerson) continue;

      if (!genreMap.has(genreKey)) {
        genreMap.set(genreKey, []);
      }
      genreMap.get(genreKey).push({ genreKey, seriesKey, data, matchedPerson });
    }

    return Array.from(genreMap.entries()).map(([genreKey, entries]) => ({
      genreKey,
      genreName: Series.getGenreName(structure, genreKey),
      entries,
    }));
  }

  /**
   * Legacy: search by project/person structure. Returns empty for new schema.
   */
  function searchPeople() { return []; }
  function getAllPeople() { return []; }
  function searchPeopleGroupedBySeries(structure, query, exactMatch) {
    return searchEntriesGroupedByGenre(structure, query, exactMatch)
      .map(g => ({ series: g.genreName, projects: g.entries.map(e => ({
        projectKey: e.seriesKey,
        projectLabel: e.data.name || e.seriesKey,
        personKey: e.matchedPerson,
        personLabel: e.matchedPerson,
        galleries: e.data.contents || [],
        extUrls: getEntryExternalLinks(e.data),
        genreKey: e.genreKey,
        seriesKey: e.seriesKey,
        data: e.data,
      })) }));
  }

  return {
    normalizeExternalUrl,
    getEntryExternalLinks,
    getPersonExternalLinks,
    matchesPersonName,
    searchEntriesGroupedByGenre,
    searchPeople,
    getAllPeople,
    searchPeopleGroupedBySeries,
  };
})();

if (typeof window !== 'undefined') {
  window.Search = Search;
}
