<#
.SYNOPSIS
    imviewer システムアップデートスクリプト

.DESCRIPTION
    maintenance_config.json に設定された URL から zip をダウンロードし、
    運用ディレクトリのシステムファイルを上書き更新する。

    ユーザーデータ・自動生成ファイルは更新対象外。

.PARAMETER DryRun
    実際のファイルコピーを行わず、コピー対象ファイルの一覧のみ表示する。

.EXAMPLE
    .\update.ps1
    .\update.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$TargetRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# パス設定
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# TargetRoot を明示的に与えられた場合はそこを更新先とする
if ($TargetRoot) {
    $RootDir = (Resolve-Path -LiteralPath $TargetRoot).ProviderPath
} else {
    $RootDir = Split-Path -Parent $ScriptDir
}
$ConfigFile = Join-Path $ScriptDir "maintenance_config.json"

# ---------------------------------------------------------------------------
# 設定ファイル読み込み
# ---------------------------------------------------------------------------
if (-not (Test-Path $ConfigFile)) {
    Write-Error "設定ファイルが見つかりません: $ConfigFile"
    exit 1
}

try {
    $Config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Error "maintenance_config.json の解析に失敗しました: $_"
    exit 1
}

$UpdateUrl = $Config.update.zip_url
if (-not $UpdateUrl -or $UpdateUrl -match "YOUR_USERNAME") {
    Write-Error @"
maintenance_config.json の update.zip_url が設定されていません。
以下のように正しい URL を設定してください:
  "update": {
    "zip_url": "https://github.com/OWNER/REPO/archive/refs/heads/main.zip"
  }
"@
    exit 1
}

# ---------------------------------------------------------------------------
# 更新対象外パス（ユーザーデータ・ユーザー設定ファイル）
#
# ※ .gitignore 管理外のファイル（auto-generated）は zip に含まれないため
#    ここでの除外指定は不要:
#      site/structure.json, site/js/gallery-pages.js, site/js/structure.js,
#      site/js/site-config.js, site/contents/, site/thumbnail/, site/banner/,
#      site/otherfile/, tools/bin/, tools/content_add/workspace 以外のサブディレクトリ
# ---------------------------------------------------------------------------
$ExcludeRelPaths = @(
    "site\sitedesign.json",       # ユーザー設定
    "site\version_data.txt",      # データバージョン（ユーザー管理）
    "site\history.txt",           # ユーザーデータ
    "tools\maintenance_config.json",  # ユーザー設定（本ファイル）
    "tools\metadata.csv"          # ユーザーデータ
)

# ---------------------------------------------------------------------------
# ヘルパー: 相対パスが除外対象かどうかを判定
# ---------------------------------------------------------------------------
function Test-Excluded {
    param([string]$RelPath)
    foreach ($ex in $ExcludeRelPaths) {
        if ($RelPath -eq $ex -or $RelPath.StartsWith($ex + "\")) {
            return $true
        }
    }
    return $false
}

# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
if ($DryRun) {
    Write-Host "[DRY RUN] 実際のファイル操作は行いません。" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "========================================"
Write-Host " imviewer アップデート"
Write-Host "========================================"
Write-Host "ダウンロード URL : $UpdateUrl"
Write-Host "更新先ディレクトリ: $RootDir"
Write-Host ""

# 一時ディレクトリ作成
$TempDir = Join-Path $env:TEMP ("imviewer_update_" + (Get-Date -Format "yyyyMMddHHmmss"))
New-Item -ItemType Directory -Path $TempDir | Out-Null

try {
    # ------------------------------------------------------------------
    # 1. zip ダウンロード
    # ------------------------------------------------------------------
    $ZipFile = Join-Path $TempDir "update.zip"
    Write-Host "[1/3] zip をダウンロード中..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $UpdateUrl -OutFile $ZipFile -UseBasicParsing
    } catch {
        Write-Error "ダウンロードに失敗しました: $_"
        exit 1
    }
    Write-Host "      完了: $ZipFile"
    Write-Host ""

    # ------------------------------------------------------------------
    # 2. zip 展開
    # ------------------------------------------------------------------
    Write-Host "[2/3] zip を展開中..." -ForegroundColor Cyan
    $ExtractDir = Join-Path $TempDir "extracted"
    Expand-Archive -Path $ZipFile -DestinationPath $ExtractDir
    Write-Host "      完了: $ExtractDir"

    # GitHub zip は {repo}-{branch}/ というトップレベルディレクトリを持つ
    # Get-ChildItem の戻り値が単一オブジェクトや $null の場合に備えて安全に配列化する
    $rawTop = Get-ChildItem -Path $ExtractDir -Directory
    if ($null -eq $rawTop) {
        Write-Error "展開結果にディレクトリが見つかりません: $ExtractDir"
        exit 1
    }
    if ($rawTop -is [System.Array]) {
        $TopDirs = $rawTop
    } else {
        $TopDirs = @($rawTop)
    }

    $topCount = $TopDirs.Count
    if ($topCount -ne 1) {
        Write-Error "展開結果のディレクトリ構造が想定と異なります（トップレベルディレクトリが $topCount 個）"
        exit 1
    }
    $SourceRoot = $TopDirs[0].FullName
    Write-Host "      展開ルート: $SourceRoot"
    Write-Host ""

    # ------------------------------------------------------------------
    # 3. ファイルコピー
    # ------------------------------------------------------------------
    Write-Host "[3/3] ファイルをコピー中..." -ForegroundColor Cyan

    $AllFiles   = Get-ChildItem -Path $SourceRoot -Recurse -File
    $CopyCount  = 0
    $SkipCount  = 0
    $LogFile = Join-Path $env:TEMP ("imviewer_update_" + (Get-Date -Format "yyyyMMddHHmmss") + ".log")
    "Update started: $(Get-Date)" | Out-File -FilePath $LogFile -Encoding UTF8
    "Download URL: $UpdateUrl" | Out-File -FilePath $LogFile -Append -Encoding UTF8
    "Target root:  $RootDir" | Out-File -FilePath $LogFile -Append -Encoding UTF8

    foreach ($File in $AllFiles) {
        # zip 内の相対パス（トップレベルディレクトリを除く）
        $RelPath = $File.FullName.Substring($SourceRoot.Length + 1)

        # 除外判定
        if (Test-Excluded $RelPath) {
            Write-Host "  [SKIP] $RelPath" -ForegroundColor DarkGray
            "$RelPath	SKIP" | Out-File -FilePath $LogFile -Append -Encoding UTF8
            $SkipCount++
            continue
        }

        $DestPath = Join-Path $RootDir $RelPath

        if ($DryRun) {
            Write-Host "  [COPY] $RelPath" -ForegroundColor Green
            "$RelPath	COPY(DRY) -> $DestPath" | Out-File -FilePath $LogFile -Append -Encoding UTF8
        } else {
            $DestParent = Split-Path -Parent $DestPath
            if (-not (Test-Path $DestParent)) {
                New-Item -ItemType Directory -Path $DestParent | Out-Null
            }
            Copy-Item -Path $File.FullName -Destination $DestPath -Force
            Write-Host "  [COPY] $RelPath" -ForegroundColor Green
            "$RelPath	COPY -> $DestPath" | Out-File -FilePath $LogFile -Append -Encoding UTF8
        }
        $CopyCount++
    }

    # ------------------------------------------------------------------
    # 結果サマリー
    # ------------------------------------------------------------------
    Write-Host ""
    Write-Host "========================================"
    if ($DryRun) {
        Write-Host " [DRY RUN] アップデート シミュレーション完了" -ForegroundColor Yellow
    } else {
        Write-Host " アップデート完了" -ForegroundColor Green
    }
    Write-Host "========================================"
    Write-Host "  コピー対象: $CopyCount ファイル"
    Write-Host "  スキップ  : $SkipCount ファイル（ユーザーデータ・設定）"
    Write-Host ""
    Write-Host "ログファイル: $LogFile"
    "Update finished: $(Get-Date)" | Out-File -FilePath $LogFile -Append -Encoding UTF8

} finally {
    # 一時ディレクトリ削除
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
