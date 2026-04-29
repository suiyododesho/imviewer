/**
 * Unit Tests for Gallery media helpers.
 * Open test-gallery.html in a browser to run.
 */

(function runGalleryUnitTests() {
  const outputLines = [];
  let passed = 0;
  let failed = 0;

  function log(line) {
    outputLines.push(line);
  }

  function assert(description, actual, expected) {
    if (JSON.stringify(actual) === JSON.stringify(expected)) {
      passed += 1;
      log(`✓ ${description}`);
    } else {
      failed += 1;
      log(`✗ ${description}`);
      log(`  expected: ${JSON.stringify(expected)}`);
      log(`  actual:   ${JSON.stringify(actual)}`);
    }
  }

  function assertTrue(description, condition) {
    if (condition) {
      passed += 1;
      log(`✓ ${description}`);
    } else {
      failed += 1;
      log(`✗ ${description}`);
    }
  }

  if (!window.GalleryUtils) {
    failed += 1;
    log('✗ GalleryUtils が読み込まれていません');
  } else {
    const utils = window.GalleryUtils;

    log('--- video extension detection ---');
    assertTrue('MP4 は動画として判定される', utils.isVideoPath('movie.MP4'));
    assertTrue('MKV は動画として判定される', utils.isVideoPath('clip.mkv'));
    assertTrue('WMV は動画として判定される', utils.isVideoPath('sample.WMV'));
    assertTrue('JPG は動画として判定されない', !utils.isVideoPath('photo.jpg'));

    log('\n--- mime type inference ---');
    assert('mp4 の MIME type', utils.inferVideoMimeType('movie.mp4'), 'video/mp4');
    assert('mpeg の MIME type', utils.inferVideoMimeType('movie.MPEG'), 'video/mpeg');
    assert('avi の MIME type', utils.inferVideoMimeType('movie.avi'), 'video/x-msvideo');
    assert('wmv の MIME type', utils.inferVideoMimeType('movie.wmv'), 'video/x-ms-wmv');

    log('\n--- page entry normalization ---');
    const imageEntry = utils.normalizeGalleryPageEntry({
      image: 'photo/sample/person/pic 01.jpg',
      html: 'photo/sample/person/index.html',
    }, 'photo/sample/person/index.html');
    assert('画像 entry は type=image', imageEntry.type, 'image');
    assert('画像 path は contents/ 配下に正規化', imageEntry.image, 'contents/photo/sample/person/pic%2001.jpg');

    const videoEntry = utils.normalizeGalleryPageEntry({
      type: 'video',
      video: 'photo/sample/person/movie 01.MKV',
      html: 'photo/sample/person/index.html',
      thumbNumber: 2,
    }, 'photo/sample/person/index.html');
    assert('動画 entry は type=video', videoEntry.type, 'video');
    assert('動画 path は contents/ 配下に正規化', videoEntry.video, 'contents/photo/sample/person/movie%2001.MKV');
    assert('動画連番が保持される', videoEntry.thumbNumber, 2);

    log('\n--- spread mode helpers ---');
    assert('不正な表示モードは single に正規化', utils.normalizeGalleryViewMode('invalid-mode'), 'single');
    assert('表示モードラベル解決', utils.getGalleryViewModeLabel('rtl-cover'), '右綴じ(表紙あり)');

    const rtlCover = utils.buildSpreadUnits(5, 'rtl-cover').map((unit) => unit.slots);
    assert('右綴じ(表紙あり) 見開き割り当て', rtlCover, [
      [null, 0],
      [2, 1],
      [4, 3],
    ]);

    const ltrNoCover = utils.buildSpreadUnits(5, 'ltr-nocover').map((unit) => unit.slots);
    assert('左綴じ(表紙なし) 見開き割り当て', ltrNoCover, [
      [0, 1],
      [2, 3],
      [4, null],
    ]);
  }

  log(`\n=== Gallery unit test result ===`);
  log(`passed: ${passed}`);
  log(`failed: ${failed}`);

  const output = outputLines.join('\n');
  console.log(output);

  const resultsEl = document.getElementById('results');
  if (resultsEl) {
    resultsEl.textContent = output;
  }

  return { passed, failed };
})();
