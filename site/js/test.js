/**
 * Navigation Test Script
 * Validates page transitions and data integrity
 */

async function runTests() {
  console.log('=== ページ遷移テスト開始 ===\n');

  let passed = 0;
  let failed = 0;

  // Test 1: structure.json の整合性
  console.log('Test 1: structure.json の読み込みと構造検証');
  try {
    const response = await fetch('/site/structure.json');
    if (!response.ok) throw new Error('Failed to fetch structure.json');
    const structure = await response.json();

    // Check structure
    const projects = Object.keys(structure);
    console.log(`  ✓ プロジェクト数: ${projects.length}`);
    
    let totalPeople = 0;
    let totalGalleries = 0;
    
    for (const project of projects) {
      const projectData = structure[project];
      const people = [];
      
      for (const [key, value] of Object.entries(projectData)) {
        if (key !== 'label' && key !== 'banner' && key !== 'series' && typeof value === 'object' && value.galleries) {
          people.push(key);
          totalGalleries += value.galleries.length;
        }
      }
      
      totalPeople += people.length;
      console.log(`    - ${projectData.label || project}: ${people.length} 人物, ${projects.length > 1 ? '...' : people.length + ' ギャラリー'}`);
    }
    
    console.log(`  ✓ 総人物数: ${totalPeople}`);
    console.log(`  ✓ 総ギャラリー数: ${totalGalleries}\n`);
    passed++;
  } catch (error) {
    console.error(`  ✗ エラー: ${error.message}\n`);
    failed++;
  }

  // Test 2: URLパラメータの生成テスト
  console.log('Test 2: URLパラメータ生成テスト');
  try {
    const response = await fetch('/site/structure.json');
    const structure = await response.json();
    
    // Sample URLs
    const sampleProject = Object.keys(structure)[0];
    const sampleProjectData = structure[sampleProject];
    
    let samplePerson = null;
    for (const [key, value] of Object.entries(sampleProjectData)) {
      if (key !== 'label' && key !== 'banner' && key !== 'series' && typeof value === 'object' && value.galleries) {
        samplePerson = { key, data: value };
        break;
      }
    }
    
    if (samplePerson && samplePerson.data.galleries.length > 0) {
      const projectParams = `project=${encodeURIComponent(sampleProject)}`;
      const personParams = `${projectParams}&person=${encodeURIComponent(samplePerson.key)}`;
      const galleryParams = `${personParams}&gallery=${encodeURIComponent(samplePerson.data.galleries[0].path)}`;
      
      console.log(`  ✓ project.html?${projectParams}`);
      console.log(`  ✓ person.html?${personParams}`);
      console.log(`  ✓ gallery.html?${galleryParams}\n`);
      passed++;
    }
  } catch (error) {
    console.error(`  ✗ エラー: ${error.message}\n`);
    failed++;
  }

  // Test 3: HTMLファイルの存在確認
  console.log('Test 3: HTMLファイルの存在確認');
  const htmlFiles = ['index.html', 'project.html', 'person.html', 'gallery.html'];
  let htmlPassed = true;
  
  for (const file of htmlFiles) {
    try {
      const response = await fetch(`/site/${file}`);
      if (response.ok) {
        console.log(`  ✓ ${file}`);
      } else {
        console.error(`  ✗ ${file} (ステータス: ${response.status})`);
        htmlPassed = false;
      }
    } catch (error) {
      console.error(`  ✗ ${file} (エラー: ${error.message})`);
      htmlPassed = false;
    }
  }
  
  if (htmlPassed) {
    console.log();
    passed++;
  } else {
    console.log();
    failed++;
  }

  // Test 4: JavaScriptファイルの存在確認
  console.log('Test 4: JavaScriptファイルの存在確認');
  const jsFiles = ['site-config.js', 'series.js', 'navigation.js', 'search.js', 'index.js', 'project.js', 'person.js', 'gallery.js'];
  let jsPassed = true;
  
  for (const file of jsFiles) {
    try {
      const response = await fetch(`/site/js/${file}`);
      if (response.ok) {
        console.log(`  ✓ js/${file}`);
      } else {
        console.error(`  ✗ js/${file} (ステータス: ${response.status})`);
        jsPassed = false;
      }
    } catch (error) {
      console.error(`  ✗ js/${file} (エラー: ${error.message})`);
      jsPassed = false;
    }
  }
  
  if (jsPassed) {
    console.log();
    passed++;
  } else {
    console.log();
    failed++;
  }

  // Test 5: CSSファイルの存在確認
  console.log('Test 5: CSSファイルの存在確認');
  try {
    const response = await fetch('/site/css/style.css');
    if (response.ok) {
      console.log(`  ✓ css/style.css\n`);
      passed++;
    } else {
      console.error(`  ✗ css/style.css (ステータス: ${response.status})\n`);
      failed++;
    }
  } catch (error) {
    console.error(`  ✗ css/style.css (エラー: ${error.message})\n`);
    failed++;
  }

  // Test 6: バナー画像の存在確認
  console.log('Test 6: バナー画像の存在確認');
  try {
    const response = await fetch('/site/structure.json');
    const structure = await response.json();
    
    let foundBanners = 0;
    for (const project of Object.values(structure)) {
      if (project.banner) {
        foundBanners++;
        try {
          const bannerResp = await fetch(`/site/${project.banner}`);
          if (bannerResp.ok) {
            console.log(`  ✓ ${project.banner}`);
          }
        } catch (e) {
          console.warn(`  ⚠ ${project.banner} (アクセス不可)`);
        }
      }
    }
    console.log(`  ✓ バナー数: ${foundBanners}\n`);
    passed++;
  } catch (error) {
    console.error(`  ✗ エラー: ${error.message}\n`);
    failed++;
  }

  // Test 7: サムネイル画像の存在確認（サンプル）
  console.log('Test 7: サムネイル画像の存在確認（サンプル）');
  try {
    const response = await fetch('/site/structure.json');
    const structure = await response.json();
    
    let checkedCount = 0;
    let foundCount = 0;
    
    for (const project of Object.values(structure)) {
      for (const person of Object.values(project)) {
        if (Array.isArray(person.galleries)) {
          for (const gallery of person.galleries) {
            if (gallery.thumbnail && checkedCount < 3) {
              checkedCount++;
              try {
                const thumbResp = await fetch(`/site/${gallery.thumbnail}`);
                if (thumbResp.ok) {
                  foundCount++;
                  console.log(`  ✓ ${gallery.thumbnail}`);
                }
              } catch (e) {
                console.warn(`  ⚠ ${gallery.thumbnail} (アクセス不可)`);
              }
            }
          }
        }
      }
    }
    console.log(`  ✓ 確認数: ${foundCount}/${checkedCount}\n`);
    passed++;
  } catch (error) {
    console.error(`  ✗ エラー: ${error.message}\n`);
    failed++;
  }

  // Summary
  console.log('=== テスト結果 ===');
  console.log(`✓ 成功: ${passed}`);
  console.log(`✗ 失敗: ${failed}`);
  console.log(`\n推奨アクション:`);
  
  if (failed === 0) {
    console.log('- すべてのテストが成功しました！');
    console.log('- ブラウザで index.html を開いてページ遷移を確認してください。');
    console.log('- 注意: ローカルファイルで開く場合、一部ブラウザでCORSエラーが発生する可能性があります。');
    console.log('- その場合は、簡易HTTPサーバーを起動してください: `python -m http.server 8000`');
  } else {
    console.log('- 上記のエラーを確認して修正してください。');
  }
}

// Run tests
runTests().catch(console.error);
