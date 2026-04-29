#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validate site structure and configuration
"""

import json
import os
from pathlib import Path

def validate_site():
    print('=' * 60)
    print('ページ遷移テスト - 検証レポート')
    print('=' * 60)
    print()
    
    base_dir = Path('.')
    
    # Test 1: File existence
    print('Test 1: ファイル存在確認')
    print('-' * 60)
    
    required_files = [
        'index.html',
        'project.html',
        'person.html',
        'gallery.html',
        'structure.json',
        'css/style.css',
        'js/navigation.js',
        'js/search.js',
        'js/index.js',
        'js/project.js',
        'js/person.js',
        'js/gallery.js'
    ]
    
    all_files_exist = True
    for file in required_files:
        path = base_dir / file
        if path.exists():
            print(f'✓ {file}')
        else:
            print(f'✗ {file} (見つかりません)')
            all_files_exist = False
    
    print()
    
    # Test 2: structure.json validation
    print('Test 2: structure.json の検証')
    print('-' * 60)
    
    try:
        with open('structure.json', 'r', encoding='utf-8') as f:
            structure = json.load(f)
        
        print('✓ JSON形式: OK')
        
        total_projects = len(structure)
        total_people = 0
        total_galleries = 0
        total_thumbnails = 0
        missing_thumbnails = []
        
        for project_key, project in structure.items():
            project_label = project.get('label', project_key)
            
            for person_key, person_value in project.items():
                if person_key not in ['label', 'banner'] and isinstance(person_value, dict) and 'galleries' in person_value:
                    total_people += 1
                    
                    for idx, gallery in enumerate(person_value.get('galleries', [])):
                        total_galleries += 1
                        
                        # Check thumbnail
                        if gallery.get('thumbnail'):
                            total_thumbnails += 1
                        else:
                            missing_thumbnails.append(f'{project_key}/{person_key} - gallery {idx}')
                        
                        # Validate gallery path exists
                        gallery_path = gallery.get('path', '')
                        if not gallery_path:
                            print(f'⚠ {project_label}/{person_key} - ギャラリーパスがありません')
        
        print(f'✓ プロジェクト数: {total_projects}')
        print(f'✓ 人物数: {total_people}')
        print(f'✓ ギャラリー数: {total_galleries}')
        print(f'✓ サムネイル数: {total_thumbnails}/{total_galleries}')
        
        if total_thumbnails == total_galleries:
            print('✓ すべてのギャラリーにサムネイルがあります')
        else:
            print(f'⚠ サムネイルなし: {len(missing_thumbnails)}件')
        
        print()
        
    except json.JSONDecodeError as e:
        print(f'✗ JSON形式エラー: {e}')
    except FileNotFoundError:
        print('✗ structure.json が見つかりません')
    
    print()
    
    # Test 3: Directory structure
    print('Test 3: ディレクトリ構造確認')
    print('-' * 60)
    
    dirs = ['css', 'js', 'banner', 'thumbnail', 'contents']
    for dir_name in dirs:
        path = base_dir / dir_name
        if path.exists() and path.is_dir():
            item_count = len(list(path.iterdir()))
            print(f'✓ {dir_name}/ ({item_count} items)')
        else:
            print(f'✗ {dir_name}/ (見つかりません)')
    
    print()
    
    # Test 4: Summary
    print('=' * 60)
    print('テスト結果サマリー')
    print('=' * 60)
    print()
    
    if all_files_exist:
        print('✓ すべての必須ファイルが存在します')
    else:
        print('✗ 一部のファイルが見つかりません')
    
    print()
    print('推奨事項:')
    print('1. HTTPサーバーを起動: python -m http.server 8080')
    print('2. ブラウザでアクセス: http://localhost:8080/test.html')
    print('3. テストツールでページ遷移を検証してください')
    print()

if __name__ == '__main__':
    validate_site()
