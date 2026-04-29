/**
 * Persons List Page Script
 * Renders a sitemap-style listing of all unique persons across all projects,
 * grouped by the first character of their name.
 * Each person links to index.html?person=<name> which shows series-grouped results.
 */

document.addEventListener('DOMContentLoaded', () => {
  try {
    if (!window.siteStructure) {
      throw new Error('Site structure not loaded. Make sure structure.js is included.');
    }

    const siteStructure = window.siteStructure;
    const siteConfig = window.siteConfig || {};

    const sidebar = document.getElementById('seriesSidebar');
    Series.renderSeriesSidebar(sidebar, siteStructure, '');

    renderPersonsList(siteStructure);
    setupSearch(siteStructure);
  } catch (error) {
    console.error('Error initializing persons page:', error);
    const container = document.getElementById('personsContainer');
    if (container) {
      container.innerHTML = `<div class="no-results">ページの読み込みに失敗しました: ${error.message}</div>`;
    }
  }
});

// ============ Rendering ============

function renderPersonsList(structure) {
  const container = document.getElementById('personsContainer');
  if (!container) {
    return;
  }

  const personMap = collectAllPersons(structure);
  if (personMap.size === 0) {
    container.innerHTML = '<div class="no-results">人物データがありません</div>';
    return;
  }

  const groups = groupPersonsByFirstChar(personMap);
  container.innerHTML = '';

  for (const [char, persons] of groups) {
    const group = document.createElement('div');
    group.className = 'persons-char-group';

    const heading = document.createElement('h3');
    heading.className = 'persons-char-heading';
    heading.textContent = char;
    group.appendChild(heading);

    const chips = document.createElement('div');
    chips.className = 'persons-chips';

    for (const { label } of persons) {
      const link = document.createElement('a');
      link.className = 'person-chip';
      link.href = `index.html?person=${encodeURIComponent(label)}`;
      link.textContent = label;
      chips.appendChild(link);
    }

    group.appendChild(chips);
    container.appendChild(group);
  }
}

// ============ Data Collection ============

/**
 * Collect all unique persons across all projects.
 * @param {Object} structure
 * @returns {Map<string, { label: string, galleryCount: number }>} keyed by label
 */
function collectAllPersons(structure) {
  const personMap = new Map();

  for (const [, project] of Object.entries(structure || {})) {
    for (const [personKey, person] of Object.entries(project)) {
      if (personKey === 'label' || personKey === 'banner' || personKey === 'series') {
        continue;
      }
      if (typeof person !== 'object' || !Array.isArray(person.galleries)) {
        continue;
      }
      const label = person.label || personKey;
      if (!personMap.has(label)) {
        personMap.set(label, { label, galleryCount: 0 });
      }
      personMap.get(label).galleryCount += person.galleries.length;
    }
  }

  return personMap;
}

/**
 * Sort persons and group by first character.
 * @param {Map<string, { label: string, galleryCount: number }>} personMap
 * @returns {Map<string, Array<{ label: string, galleryCount: number }>>}
 */
function groupPersonsByFirstChar(personMap) {
  const sorted = Array.from(personMap.values()).sort((a, b) =>
    a.label.localeCompare(b.label, 'ja')
  );

  const groups = new Map();
  for (const person of sorted) {
    const char = person.label.charAt(0);
    if (!groups.has(char)) {
      groups.set(char, []);
    }
    groups.get(char).push(person);
  }

  return groups;
}

// ============ Search ============

function setupSearch(structure) {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) {
    return;
  }

  searchInput.addEventListener('input', (event) => {
    const query = event.target.value.trim();
    if (query.length === 0) {
      return;
    }
    // Navigate to index page to show series-grouped results
    window.location.href = `index.html?person=${encodeURIComponent(query)}`;
  });

  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      const query = searchInput.value.trim();
      if (query.length > 0) {
        window.location.href = `index.html?person=${encodeURIComponent(query)}`;
      }
    }
  });
}
