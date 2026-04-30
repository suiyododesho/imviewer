/**
 * Search Utility Module
 * Provides search functionality for persons and series entries.
 */

const Search = (() => {

  const DEFAULT_SERIES_LABEL = '作品';
  const DEFAULT_CONTENT_LABEL = 'コンテンツ';
  const DEFAULT_PERSON_LABEL = '人物';

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

  function normalizeSearchTerm(raw) {
    return String(raw || '').trim().toLowerCase();
  }

  function matchesSearchTerm(value, term, exactMatch) {
    const normalized = normalizeSearchTerm(value);
    if (!term || !normalized) return false;
    return exactMatch ? normalized === term : normalized.includes(term);
  }

  function uniqueStrings(values) {
    const seen = new Set();
    const result = [];
    for (const raw of values || []) {
      if (typeof raw !== 'string') continue;
      const trimmed = raw.trim();
      if (!trimmed || seen.has(trimmed)) continue;
      seen.add(trimmed);
      result.push(trimmed);
    }
    return result;
  }

  function getGenreRuntimeConfig(structure, genreKey) {
    const { classKeys, classNames, browse } = Series.getGenreClassConfig(structure, genreKey);
    const configured = Series.getGenreSearchConfig(structure, genreKey);

    let keys = configured.keys.slice();
    let names = configured.names.slice();

    if (keys.length === 0) {
      const fallbackPersonKey = classKeys[0] || 'main-person';
      const fallbackLeafKey = browse.leafType === 'content' ? 'name' : 'series';
      keys = uniqueStrings([fallbackPersonKey, fallbackLeafKey]);
      names = keys.map((key) => {
        if (key === fallbackPersonKey) return classNames[0] || DEFAULT_PERSON_LABEL;
        return browse.leafType === 'content' ? DEFAULT_CONTENT_LABEL : DEFAULT_SERIES_LABEL;
      });
    }

    const keyDefs = keys.map((key, index) => ({
      id: `genre:${genreKey}:${key}:${index}`,
      key,
      label: names[index] || key,
      getValues: (entry) => extractEntryValuesForKey(entry, key),
      buildLeafItems: (entry) => buildLeafItemsForEntry(entry, browse.leafType),
    }));

    return {
      browse,
      classNames,
      keyDefs,
    };
  }

  function resolveLeafLabelForGenre(structure, genreKey, leafType) {
    const runtime = getGenreRuntimeConfig(structure, genreKey);
    const searchKeyMatch = runtime.keyDefs.find((def) => {
      if (leafType === 'content') return def.key === 'name';
      return def.key === 'series';
    });
    if (searchKeyMatch && searchKeyMatch.label) return searchKeyMatch.label;
    return leafType === 'content' ? DEFAULT_CONTENT_LABEL : DEFAULT_SERIES_LABEL;
  }

  function buildKeyDefsForGlobalSearch(structure, entries) {
    const personLabels = new Set();
    const leafSeriesLabels = new Set();
    const leafContentLabels = new Set();

    for (const entry of entries) {
      const runtime = getGenreRuntimeConfig(structure, entry.genreKey);
      personLabels.add(runtime.classNames[0] || DEFAULT_PERSON_LABEL);
      if (runtime.browse.leafType === 'content') {
        leafContentLabels.add(resolveLeafLabelForGenre(structure, entry.genreKey, 'content'));
      } else {
        leafSeriesLabels.add(resolveLeafLabelForGenre(structure, entry.genreKey, 'series'));
      }
    }

    const defs = [];
    defs.push({
      id: 'global:main-person',
      key: 'main-person',
      label: Array.from(personLabels).join('/') || DEFAULT_PERSON_LABEL,
      getValues: (entry) => extractEntryValuesForKey(entry, 'main-person'),
      buildLeafItems: (entry) => {
        const runtime = getGenreRuntimeConfig(structure, entry.genreKey);
        return buildLeafItemsForEntry(entry, runtime.browse.leafType);
      },
    });

    if (leafSeriesLabels.size > 0) {
      defs.push({
        id: 'global:leaf-series',
        key: '__leaf-series',
        label: Array.from(leafSeriesLabels).join('/') || DEFAULT_SERIES_LABEL,
        getValues: (entry) => {
          const runtime = getGenreRuntimeConfig(structure, entry.genreKey);
          if (runtime.browse.leafType !== 'series') return [];
          return extractEntryValuesForKey(entry, 'series');
        },
        buildLeafItems: (entry) => buildLeafItemsForEntry(entry, 'series'),
      });
    }

    if (leafContentLabels.size > 0) {
      defs.push({
        id: 'global:leaf-content',
        key: '__leaf-content',
        label: Array.from(leafContentLabels).join('/') || DEFAULT_CONTENT_LABEL,
        getValues: (entry) => {
          const runtime = getGenreRuntimeConfig(structure, entry.genreKey);
          if (runtime.browse.leafType !== 'content') return [];
          return extractEntryValuesForKey(entry, 'name');
        },
        buildLeafItems: (entry) => buildLeafItemsForEntry(entry, 'content'),
      });
    }

    return defs;
  }

  function extractEntryValuesForKey(entry, key) {
    const data = entry && entry.data;
    if (!data || !key) return [];

    if (key === 'series') {
      const seriesName = Series.getSeriesName(data);
      const title = typeof data.name === 'string' ? data.name.trim() : '';
      return uniqueStrings([seriesName, title]);
    }

    if (key === 'name') {
      const title = typeof data.name === 'string' ? data.name.trim() : '';
      return title ? [title] : [];
    }

    if (key === 'persons') {
      return uniqueStrings(Array.isArray(data.persons) ? data.persons : []);
    }

    if (key === 'contents') {
      const names = Array.isArray(data.contents)
        ? data.contents.map((content) => (content && typeof content.name === 'string') ? content.name : '')
        : [];
      return uniqueStrings(names);
    }

    if (key === 'main-person') {
      const values = Series.getEntryClassValues(data, 'main-person');
      if (values.length > 0) return values;
      const main = Series.getMainPerson(data);
      return main ? [main] : [];
    }

    return Series.getEntryClassValues(data, key);
  }

  function buildLeafItemsForEntry(entry, leafType) {
    if (!entry || !entry.data) return [];

    if (leafType === 'content') {
      const contents = Array.isArray(entry.data.contents) ? entry.data.contents : [];
      return contents.map((content) => ({
        id: `${entry.genreKey}::${entry.seriesKey}::${content.path || content.name || ''}`,
        type: 'content',
        genreKey: entry.genreKey,
        seriesKey: entry.seriesKey,
        data: entry.data,
        content,
      }));
    }

    return [{
      id: `${entry.genreKey}::${entry.seriesKey}`,
      type: 'series',
      genreKey: entry.genreKey,
      seriesKey: entry.seriesKey,
      data: entry.data,
    }];
  }

  function searchEntriesByConfiguredKeys(structure, query, options = {}) {
    const term = normalizeSearchTerm(query);
    if (!term) return { facets: [] };

    const genreKey = typeof options.genreKey === 'string' ? options.genreKey : '';
    const genreSpecified = !!options.genreSpecified;
    const exactMatch = !!options.exactMatch;

    const entries = genreSpecified && genreKey
      ? Object.entries(Series.getSeriesEntries(structure, genreKey))
        .map(([seriesKey, data]) => ({ genreKey, seriesKey, data }))
      : Series.getAllSeriesEntries(structure);

    const keyDefs = genreSpecified && genreKey
      ? getGenreRuntimeConfig(structure, genreKey).keyDefs
      : buildKeyDefsForGlobalSearch(structure, entries);

    const facets = [];

    for (const keyDef of keyDefs) {
      const groupMap = new Map();

      for (const entry of entries) {
        const values = uniqueStrings(keyDef.getValues(entry));
        for (const value of values) {
          if (!matchesSearchTerm(value, term, exactMatch)) continue;

          if (!groupMap.has(value)) {
            groupMap.set(value, {
              value,
              itemMap: new Map(),
            });
          }

          const group = groupMap.get(value);
          const leafItems = keyDef.buildLeafItems(entry);
          for (const item of leafItems) {
            group.itemMap.set(item.id, item);
          }
        }
      }

      if (groupMap.size === 0) continue;

      const valueGroups = Array.from(groupMap.values())
        .map((group) => ({
          value: group.value,
          count: group.itemMap.size,
          items: Array.from(group.itemMap.values()),
        }))
        .sort((a, b) => a.value.localeCompare(b.value, 'ja'));

      const facetItemIds = new Set();
      for (const group of valueGroups) {
        for (const item of group.items) {
          facetItemIds.add(item.id);
        }
      }

      facets.push({
        id: keyDef.id,
        key: keyDef.key,
        label: keyDef.label,
        hitCount: facetItemIds.size,
        valueGroups,
      });
    }

    return { facets };
  }

  function getSearchPlaceholder(structure, genreKey, genreSpecified) {
    const entries = genreSpecified && genreKey
      ? Object.entries(Series.getSeriesEntries(structure, genreKey))
        .map(([seriesKey, data]) => ({ genreKey, seriesKey, data }))
      : Series.getAllSeriesEntries(structure);

    const keyDefs = genreSpecified && genreKey
      ? getGenreRuntimeConfig(structure, genreKey).keyDefs
      : buildKeyDefsForGlobalSearch(structure, entries);

    const labels = uniqueStrings(keyDefs.map((item) => item.label));
    return labels.join('、') || DEFAULT_PERSON_LABEL;
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
    const result = searchEntriesByConfiguredKeys(structure, query, {
      genreSpecified: false,
      exactMatch: !!exactMatch,
    });

    if (!result.facets.length) return [];

    const genreMap = new Map();
    const fallbackFacet = result.facets[0];
    for (const group of fallbackFacet.valueGroups) {
      for (const item of group.items) {
        if (!item || !item.genreKey || !item.seriesKey || !item.data) continue;
        if (!genreMap.has(item.genreKey)) {
          genreMap.set(item.genreKey, []);
        }
        genreMap.get(item.genreKey).push({
          genreKey: item.genreKey,
          seriesKey: item.seriesKey,
          data: item.data,
          matchedPerson: group.value,
        });
      }
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
    getSearchPlaceholder,
    searchEntriesByConfiguredKeys,
    searchEntriesGroupedByGenre,
    searchPeople,
    getAllPeople,
    searchPeopleGroupedBySeries,
  };
})();

if (typeof window !== 'undefined') {
  window.Search = Search;
}
