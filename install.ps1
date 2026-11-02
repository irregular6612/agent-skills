# agent-skills bootstrap for Windows (PowerShell 5+). Not yet verified on Windows.
#
#   irm https://raw.githubusercontent.com/irregular6612/agent-skills/master/install.ps1 | iex
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/irregular6612/agent-skills/master/install.ps1))) install ditto-writer
#
# Clones (or fast-forwards) the repo into $env:AGENT_SKILLS_DIR (default ~\.agent-skills\repo)
# and runs install.py. On Windows items are copied unless Developer Mode allows symlinks
# and you pass --mode link.
$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:AGENT_SKILLS_REPO) { $env:AGENT_SKILLS_REPO } else { "https://github.com/irregular6612/agent-skills.git" }
$Dir = if ($env:AGENT_SKILLS_DIR) { $env:AGENT_SKILLS_DIR } else { Join-Path $HOME ".agent-skills\repo" }

$Py = $null
foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
  $exe = Get-Command $cand[0] -ErrorAction SilentlyContinue
  if ($exe) {
    $extra = @($cand | Select-Object -Skip 1)
    & $cand[0] @extra -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>$null
    if ($LASTEXITCODE -eq 0) { $Py = $cand; break }
  }
}
if (-not $Py) { throw "agent-skills: Python 3.9+ is required (winget install Python.Python.3.12)." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "agent-skills: git is required (winget install Git.Git)." }

$Local = if ($PSScriptRoot) { Join-Path $PSScriptRoot "install.py" } else { $null }
if ($Local -and (Test-Path $Local)) {
  $Dir = $PSScriptRoot
} elseif (Test-Path (Join-Path $Dir ".git")) {
  Write-Host "agent-skills: updating $Dir"
  git -C $Dir pull --ff-only --quiet
} else {
  Write-Host "agent-skills: cloning $RepoUrl -> $Dir"
  New-Item -ItemType Directory -Force -Path (Split-Path $Dir) | Out-Null
  git clone --quiet --depth 1 $RepoUrl $Dir
}

$extra = @($Py | Select-Object -Skip 1)
& $Py[0] @extra (Join-Path $Dir "install.py") @args
exit $LASTEXITCODE
