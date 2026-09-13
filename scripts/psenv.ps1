[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("list", "current", "use")]
    [string]$Action = "current",

    [Parameter(Position = 1)]
    [string]$Environment,

    [switch]$Auth
)

$apiScript = Join-Path $PSScriptRoot "peoplesoft_api.py"

if ($Action -eq "use" -and [string]::IsNullOrWhiteSpace($Environment)) {
    throw "Usage: .\psenv.ps1 use <environment> [-Auth]"
}

if ($Action -ne "use" -and $Auth) {
    throw "-Auth is only valid with use"
}

$cliArgs = @("env", $Action)
if ($Action -eq "use") {
    $cliArgs += $Environment
}
if ($Auth) {
    $cliArgs += "--auth"
}

& python $apiScript @cliArgs
exit $LASTEXITCODE
