<#
.SYNOPSIS
    Create a git worktree pre-configured for a parallel agent session.

.DESCRIPTION
    Adds a new worktree as a sibling of the repo at ..\eq_s3d-worktrees\<Branch>,
    creating a new branch off <BaseBranch>. It then bootstraps the gitignored
    files that a fresh worktree lacks:
      - copies .env from the main worktree (if present)
      - sets up web/node_modules (shared via junction by default, or isolated)
      - optionally creates a per-worktree Python .venv and installs requirements

.PARAMETER Branch
    Name of the new branch / worktree, e.g. "agent/cave-refactor".

.PARAMETER BaseBranch
    Branch to fork from. Defaults to "master".

.PARAMETER Venv
    Create an isolated .venv in the worktree and pip install requirements.txt.
    Omit to share the global Python environment.

.PARAMETER IsolateNode
    Run a fresh `npm install` in the worktree instead of sharing node_modules
    via a junction. Use this when the branch changes web/package.json.

.EXAMPLE
    .\scripts\new-worktree.ps1 -Branch agent/multi-level

.EXAMPLE
    .\scripts\new-worktree.ps1 -Branch agent/web-ui -Venv -IsolateNode
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Branch,

    [string]$BaseBranch = "master",

    [switch]$Venv,

    [switch]$IsolateNode
)

$ErrorActionPreference = "Stop"

# Resolve the main repo root regardless of where the script is invoked from.
$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) { throw "Not inside a git repository." }
$repoRoot = (Resolve-Path $repoRoot).Path

# Sibling location: ..\eq_s3d-worktrees\<sanitized-branch>
$leaf        = ($Branch -replace '[\\/:]', '-')
$worktreeDir = Join-Path (Split-Path $repoRoot -Parent) "eq_s3d-worktrees"
$worktreePath = Join-Path $worktreeDir $leaf

if (Test-Path $worktreePath) {
    throw "Worktree path already exists: $worktreePath"
}
New-Item -ItemType Directory -Path $worktreeDir -Force | Out-Null

Write-Host "Creating worktree '$Branch' from '$BaseBranch' at $worktreePath" -ForegroundColor Cyan
git -C $repoRoot worktree add -b $Branch $worktreePath $BaseBranch

# --- .env ------------------------------------------------------------------
$srcEnv = Join-Path $repoRoot ".env"
if (Test-Path $srcEnv) {
    Copy-Item $srcEnv (Join-Path $worktreePath ".env")
    Write-Host "Copied .env into worktree." -ForegroundColor Green
} else {
    Write-Host "No .env in main worktree; skipping (procedural defaults will apply)." -ForegroundColor Yellow
}

# --- web/node_modules ------------------------------------------------------
$srcNode = Join-Path $repoRoot "web\node_modules"
$dstNode = Join-Path $worktreePath "web\node_modules"
if ($IsolateNode) {
    Write-Host "Installing web dependencies (isolated)..." -ForegroundColor Cyan
    Push-Location (Join-Path $worktreePath "web")
    try { npm install } finally { Pop-Location }
} elseif (Test-Path $srcNode) {
    New-Item -ItemType Junction -Path $dstNode -Target $srcNode | Out-Null
    Write-Host "Linked web/node_modules via junction (shared with main worktree)." -ForegroundColor Green
} else {
    Write-Host "No web/node_modules to share; run 'npm install' in web/ when needed." -ForegroundColor Yellow
}

# --- Python .venv ----------------------------------------------------------
if ($Venv) {
    Write-Host "Creating isolated .venv and installing requirements..." -ForegroundColor Cyan
    Push-Location $worktreePath
    try {
        python -m venv .venv
        & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
        & ".\.venv\Scripts\pip.exe" install -r requirements.txt
    } finally { Pop-Location }
    Write-Host "Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
} else {
    Write-Host "Sharing global Python environment (no .venv created)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. New worktree ready:" -ForegroundColor Cyan
Write-Host "  $worktreePath" -ForegroundColor White
Write-Host "Point an agent at that folder. Remove it later with:" -ForegroundColor Cyan
Write-Host "  .\scripts\remove-worktree.ps1 -Branch $Branch -DeleteBranch" -ForegroundColor White
Write-Host "  (do NOT use a bare 'git worktree remove' — it follows the" -ForegroundColor DarkYellow
Write-Host "   node_modules junction and deletes the MAIN repo's modules)" -ForegroundColor DarkYellow
