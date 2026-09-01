#!/bin/bash
# Watches the whole "personal website" vault folder (Writing/*.md and
# bookmarks.md together) recursively. On a quiet period after a change,
# builds and -- if anything changed -- commits writing.html, writing/, and
# bookmarks.html locally. Never runs git push: that's the user's own step,
# on purpose, so nothing here ever needs GitHub auth.
set -u

REPO="/home/kaelorvale/Projects/personal website/Dashrath-Kunwar.github.io"
VAULT_DIR="$HOME/NOTES/Batcave/personal website"
PYTHON="/home/kaelorvale/.local/share/mise/installs/python/latest/bin/python3"
BUILD="$REPO/tools/build.py"
DEBOUNCE_SECS=3

run_build() {
  local output status
  output="$("$PYTHON" "$BUILD" 2>&1)"
  status=$?
  if [ "$status" -ne 0 ]; then
    notify-send -u critical "Website publish failed" "$output"
    return
  fi
  [ "$output" = "nothing to do" ] && return

  cd "$REPO" || return
  mkdir -p writing  # git add fails outright on a path that doesn't exist yet
  git add writing.html writing/ bookmarks.html
  git diff --cached --quiet && return

  local changed
  changed="$(git diff --cached --name-only | tr '\n' ' ')"
  git commit -q -m "Publish: $changed"
  notify-send "Website published" "Committed locally — run git push when ready."
}

# debounce: any inotify event resets the timer; only a DEBOUNCE_SECS quiet
# gap with no further writes triggers a build (Obsidian autosaves on every
# pause, and saves via an atomic rename, so a single edit fires several events)
dirty=0
while :; do
  # capture $? from read immediately -- after `if COND; then ...; fi` with no
  # else and a false COND, bash resets $? to 0, so it must be grabbed here,
  # not after the if/fi
  read -r -t "$DEBOUNCE_SECS" _
  status=$?
  if [ "$status" -eq 0 ]; then
    dirty=1
    continue
  fi
  if [ "$status" -gt 128 ]; then
    [ "$dirty" -eq 1 ] && run_build
    dirty=0
    continue
  fi
  # real EOF -- inotifywait died. exit non-zero so systemd restarts us.
  exit 1
done < <(inotifywait -m -q -r -e close_write,moved_to,moved_from,delete "$VAULT_DIR")
