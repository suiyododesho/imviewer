/**
 * Unit Tests for Search Module
 * Tests searchPeopleGroupedBySeries and persons page helpers (collectAllPersons, groupPersonsByFirstChar).
 * Run standalone in browser (no server required): open test-search.html or include this file.
 */

(function runSearchUnitTests() {
  const MOCK_STRUCTURE = {
    honey2: {
      label: 'Juicy Honey #2',
      banner: 'banner/honey002.jpg',
      series: 'Juicy Honey',
      '薫まい': {
        label: '薫まい',
        exturl: [
          { caption: 'プロフィール', url: 'photo/honey2/薫まい 01/index_薫まい 01.html' },
          { caption: 'Wikipedia', url: 'https://example.com/kaoru' },
        ],
        galleries: [
          { thumbnail: 'thumbnail/h2_kaoru_001.jpg', path: 'photo/honey2/薫まい 01/index.html' },
          { thumbnail: 'thumbnail/h2_kaoru_002.jpg', path: 'photo/honey2/薫まい 02/index.html' },
        ],
      },
      '山口まゆ': {
        label: '山口まゆ',
        galleries: [
          { thumbnail: 'thumbnail/h2_mayu_001.jpg', path: 'photo/honey2/山口まゆ 01/index.html' },
        ],
      },
    },
    honey4: {
      label: 'Juicy Honey #4',
      banner: 'banner/honey004.jpg',
      series: 'Juicy Honey',
      '薫まい': {
        label: '薫まい',
        galleries: [
          { thumbnail: 'thumbnail/h4_kaoru_001.jpg', path: 'photo/honey4/薫まい 01/index.html' },
        ],
      },
    },
    'aneone-p18': {
      label: '姉ワン #18',
      banner: 'banner/aneone18.jpg',
      series: '姉ワンスタイル',
      'あずみひな': {
        label: 'あずみひな',
        galleries: [
          { thumbnail: 'thumbnail/aneone18_hina_001.jpg', path: 'photo/aneone-p18/あずみひな/index_あずみひな.html' },
        ],
      },
    },
    uncategorized_proj: {
      label: '未分類Project',
      '田中花子': {
        label: '田中花子',
        galleries: [
          { thumbnail: 'thumbnail/tanaka_001.jpg', path: 'photo/uncategorized_proj/田中花子/index.html' },
        ],
      },
    },
  };

  let passed = 0;
  let failed = 0;
  const results = [];

  function assert(description, actual, expected) {
    if (JSON.stringify(actual) === JSON.stringify(expected)) {
      passed++;
      results.push(`  ✓ ${description}`);
    } else {
      failed++;
      results.push(`  ✗ ${description}`);
      results.push(`      expected: ${JSON.stringify(expected)}`);
      results.push(`      actual:   ${JSON.stringify(actual)}`);
    }
  }

  function assertTrue(description, value) {
    if (value) {
      passed++;
      results.push(`  ✓ ${description}`);
    } else {
      failed++;
      results.push(`  ✗ ${description} (got falsy: ${JSON.stringify(value)})`);
    }
  }

  // ============ searchPeopleGroupedBySeries ============

  results.push('\n--- searchPeopleGroupedBySeries ---');

  // Empty query returns empty array
  assert(
    '空クエリは空配列を返す',
    Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, ''),
    []
  );
  assert(
    'スペースのみのクエリは空配列を返す',
    Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '   '),
    []
  );

  // Prefix match: 薫 → hits 薫まい in honey2 and honey4 (both Juicy Honey)
  (function testKaoruPrefix() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '薫');
    assertTrue('「薫」前方一致: 1シリーズ(Juicy Honey)', res.length === 1);
    if (res.length > 0) {
      assert('シリーズ名が正しい', res[0].series, 'Juicy Honey');
      assertTrue('2プロジェクトがヒット (honey2, honey4)', res[0].projects.length === 2);
      assert('honey2の人物ラベル', res[0].projects[0].personLabel, '薫まい');
      assert('honey4の人物ラベル', res[0].projects[1].personLabel, '薫まい');
      assert('honey2 exturl 1件目はcontents起点に正規化される', res[0].projects[0].extUrls[0].url, 'contents/photo/honey2/薫まい 01/index_薫まい 01.html');
      assert('honey2 exturl 2件目は絶対URLを維持する', res[0].projects[0].extUrls[1].url, 'https://example.com/kaoru');
    }
  })();

  // Prefix match spanning multiple series: '山' → only 山口まゆ in Juicy Honey
  (function testYamaguchiPrefix() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '山');
    assertTrue('「山」前方一致: 1シリーズ', res.length === 1);
    if (res.length > 0) {
      assert('シリーズ名はJuicy Honey', res[0].series, 'Juicy Honey');
      assert('1プロジェクトがヒット', res[0].projects.length, 1);
    }
  })();

  // Prefix match across multiple series: 'あ' → あずみひな (姉ワンスタイル)
  (function testAzumiPrefix() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, 'あ');
    assertTrue('「あ」前方一致: 1シリーズ(姉ワンスタイル)', res.length === 1);
    if (res.length > 0) {
      assert('シリーズ名は姉ワンスタイル', res[0].series, '姉ワンスタイル');
    }
  })();

  // Partial match: まい → 薫まい in honey2 and honey4
  (function testKaoruPartial() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, 'まい');
    assertTrue('「まい」部分一致: 1シリーズ(Juicy Honey)', res.length === 1);
    if (res.length > 0) {
      assert('シリーズ名が正しい', res[0].series, 'Juicy Honey');
      assertTrue('2プロジェクトがヒット (honey2, honey4)', res[0].projects.length === 2);
    }
  })();

  // Uncategorized project (no series key)
  (function testUncategorized() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '田中');
    assertTrue('未分類projectがヒット', res.length === 1);
    if (res.length > 0) {
      assert('シリーズ名は未分類', res[0].series, '未分類');
    }
  })();

  // exactMatch = true: exact name match only
  (function testExactMatch() {
    const resExact = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '薫まい', true);
    assertTrue('exactMatch: 「薫まい」完全一致ヒット', resExact.length === 1);

    const resNoMatch = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, '薫', true);
    assert('exactMatch: 「薫」(前方一致相当)はヒットしない', resNoMatch, []);
  })();

  // No match
  (function testNoMatch() {
    const res = Search.searchPeopleGroupedBySeries(MOCK_STRUCTURE, 'zzz_notexist');
    assert('存在しない名前はヒットしない', res, []);
  })();

  // ============ collectAllPersons (persons.js helper - if available) ============

  results.push('\n--- exturl helpers ---');
  assert('relative exturl is normalized to contents root', Search.normalizeExternalUrl('photo/a/b.html'), 'contents/photo/a/b.html');
  assert('contents-prefixed exturl stays as-is', Search.normalizeExternalUrl('contents/photo/a/b.html'), 'contents/photo/a/b.html');
  assert('https exturl stays as-is', Search.normalizeExternalUrl('https://example.com'), 'https://example.com');

  if (typeof collectAllPersons !== 'undefined') {
    results.push('\n--- collectAllPersons ---');

    const map = collectAllPersons(MOCK_STRUCTURE);
    assertTrue('全ユニーク人物数: 4 (薫まい、山口まゆ、あずみひな、田中花子)', map.size === 4);
    assertTrue('「薫まい」のギャラリー数: 3 (honey2×2 + honey4×1)', map.get('薫まい')?.galleryCount === 3);
    assertTrue('「山口まゆ」のギャラリー数: 1', map.get('山口まゆ')?.galleryCount === 1);
  }

  // ============ groupPersonsByFirstChar (persons.js helper - if available) ============

  if (typeof groupPersonsByFirstChar !== 'undefined') {
    results.push('\n--- groupPersonsByFirstChar ---');

    const mockMap = new Map([
      ['薫まい', { label: '薫まい', galleryCount: 3 }],
      ['山口まゆ', { label: '山口まゆ', galleryCount: 1 }],
      ['あずみひな', { label: 'あずみひな', galleryCount: 1 }],
      ['田中花子', { label: '田中花子', galleryCount: 1 }],
    ]);

    const groups = groupPersonsByFirstChar(mockMap);
    assertTrue('グループが存在する', groups.size > 0);
    assertTrue('「あ」グループに「あずみひな」が含まれる', groups.get('あ')?.some(p => p.label === 'あずみひな'));
    assertTrue('「薫」グループに「薫まい」が含まれる', groups.get('薫')?.some(p => p.label === '薫まい'));
  }

  // ============ Summary ============

  results.push(`\n=== 検索ユニットテスト結果 ===`);
  results.push(`✓ 成功: ${passed}`);
  results.push(`✗ 失敗: ${failed}`);

  const output = results.join('\n');
  console.log(output);

  return { passed, failed };
})();
