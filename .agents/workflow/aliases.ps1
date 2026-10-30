# Load once per shell with: . ./.agents/workflow/aliases.ps1
function on {
    if ($args.Count -gt 0) {
        throw 'Usage: on'
    }
    gh workflow run availability.yml -f status=working
}

function off {
    param([string]$Login)
    if ($args.Count -gt 0 -or ($PSBoundParameters.ContainsKey('Login') -and [string]::IsNullOrWhiteSpace($Login))) {
        throw 'Usage: off [GITHUB_LOGIN]'
    }
    if ($PSBoundParameters.ContainsKey('Login')) {
        gh workflow run availability.yml -f status=away -f "login=$Login"
    } else {
        gh workflow run availability.yml -f status=away
    }
}
