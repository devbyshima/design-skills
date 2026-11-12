#!/usr/bin/env bash
set -euo pipefail

# Symlink every skill in this repo into the local skill directories each agent
# harness reads:
#   - ~/.claude/skills  — Claude Code
#   - ~/.agents/skills  — pi and other Agent-Skills-standard harnesses
# Each entry is a symlink into this repo, so `git pull` keeps installed skills
# up to date. (For a one-off managed install instead, use `npx skills add devbyshima/design-skills`.)

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DESTS=("$HOME/.claude/skills" "$HOME/.agents/skills")

# Collect the repo's skills once (skip the deprecated/ holding area).
names=()
srcs=()
while IFS= read -r -d '' skill_md; do
  src="$(dirname "$skill_md")"
  names+=("$(basename "$src")")
  srcs+=("$src")
done < <(find "$REPO/skills" -name SKILL.md -not -path '*/node_modules/*' -not -path '*/deprecated/*' -print0)

for DEST in "${DESTS[@]}"; do
  # If $DEST is itself a symlink into this repo, linking would write the per-skill
  # symlinks back into the repo. Detect and bail rather than pollute the tree.
  if [ -L "$DEST" ]; then
    resolved="$(readlink -f "$DEST" 2>/dev/null || echo "$DEST")"
    case "$resolved" in
      "$REPO"|"$REPO"/*)
        echo "error: $DEST is a symlink into this repo ($resolved)." >&2
        echo "Remove it (rm \"$DEST\") and re-run; it will be recreated as a real dir." >&2
        exit 1
        ;;
    esac
  fi

  mkdir -p "$DEST"
  for i in "${!names[@]}"; do
    name="${names[$i]}"
    src="${srcs[$i]}"
    target="$DEST/$name"
    [ -e "$target" ] && [ ! -L "$target" ] && rm -rf "$target"
    ln -sfn "$src" "$target"
    echo "linked $name -> $src ($DEST)"
  done
done
