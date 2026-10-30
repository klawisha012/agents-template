# Load once per shell with: source .agents/workflow/aliases.sh
on() {
  if [ "$#" -ne 0 ]; then
    echo 'Usage: on' >&2
    return 2
  fi
  gh workflow run availability.yml -f status=working
}

off() {
  if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ -z "$1" ]; }; then
    echo 'Usage: off [GITHUB_LOGIN]' >&2
    return 2
  fi
  if [ "$#" -eq 0 ]; then
    gh workflow run availability.yml -f status=away
  else
    gh workflow run availability.yml -f status=away -f "login=$1"
  fi
}
