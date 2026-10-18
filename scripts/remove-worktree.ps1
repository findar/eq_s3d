<#
.SYNOPSIS
    Safely tear down a worktree created by new-worktree.ps1.

.DESCRIPTION
    MUST be used instead of a bare `git worktree remove` when the worktree was
    created with a shared node_modules junction. `git worktree remove` on Windows
    follows the junction and deletes files inside the MAIN repo's node_modules
    (the junction target), which can gut the primary checkout. This script first
    unlinks the junction AS A LINK (cmd `rmdir`, which does not recurse into the
    target), then removes the worktree, prunes git's admin, and optionally
    deletes the branch.

.PARAMETER Branch
    The branch / worktree to remove, e.g. "agent/multi-level". The worktree path
    is derived the same way new-worktree.ps1 derives it.

.PARAMETER DeleteBranch
    Also delete the local branch after the worktree is removed (uses `-d`, which
    refuses unmerged branches unless -Force is given).

.PARAMETER Force
    Pass --force to `git worktree remove` (discards uncommitted changes in the
    worktree) and use `-D` for the branch delete.

.EXAMPLE
    .\scripts\remove-worktree.ps1 -Branch agent/multi-level -DeleteBranch
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Branch,

    [switch]$DeleteBranch,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) { throw "Not inside a git repository." }
$repoRoot = (Resolve-Path $repoRoot).Path

$leaf         = ($Branch -replace '[\\/:]', '-')
$worktreePath = Join-Path (Join-Path (Split-Path $repoRoot -Parent) "eq_s3d-worktrees") $leaf

if (-not (Test-Path $worktreePath)) {
    Write-Host "Worktree path not found: $worktreePath" -ForegroundColor Yellow
    Write-Host "Running 'git worktree prune' in case the entry is stale." -ForegroundColor Yellow
    git -C $repoRoot worktree prune
    return
}

# --- 1. Unlink any shared junctions FIRST, as links (never recurse) --------
# new-worktree.ps1 only creates web\node_modules as a junction; handle it
# explicitly so we never follow a reparse point into the main checkout.
$junction = Join-Path $worktreePath "web\node_modules"
if (Test-Path $junction) {
    $item = Get-Item $junction -Force
    if ($item.LinkType -eq "Junction" -or $item.LinkType -eq "SymbolicLink") {
        Write-Host "Unlinking junction: $junction" -ForegroundColor Cyan
        cmd /c rmdir "$((Resolve-Path $junction).Path)"
        if ($LASTEXITCODE -ne 0) { throw "Failed to unlink junction at $junction" }
    } else {
        Write-Host "web\node_modules is a real directory (isolated), leaving git to remove it." -ForegroundColor Yellow
    }
}

# --- 2. Remove the worktree (now safe — no junction to follow) -------------
Write-Host "Removing worktree: $worktreePath" -ForegroundColor Cyan
if ($Force) {
    git -C $repoRoot worktree remove --force $worktreePath
} else {
    git -C $repoRoot worktree remove $worktreePath
}

# Belt-and-braces: if git left the dir behind, clear it (junction already gone).
if (Test-Path $worktreePath) {
    Remove-Item -Recurse -Force $worktreePath
}

git -C $repoRoot worktree prune

# --- 3. Optionally delete the branch ---------------------------------------
if ($DeleteBranch) {
    $flag = if ($Force) { "-D" } else { "-d" }
    Write-Host "Deleting branch '$Branch' ($flag)" -ForegroundColor Cyan
    git -C $repoRoot branch $flag $Branch
}

Write-Host "Worktree '$Branch' removed cleanly." -ForegroundColor Green
