#!/usr/bin/env bash
set -euo pipefail

# List every skill in the repo as: <category>/<name>  —  <description>
# (excludes the deprecated/ holding area).

REPO="$(cd "$(dirname "$0")/.." && pwd)"

find "$REPO/skills" -name SKILL.md -not -path '*/node_modules/*' -not -path '*/deprecated/*' \
  | sort | while IFS= read -r f; do
    dir="${f%/SKILL.md}"
    rel="${dir#"$REPO"/skills/}"
    name="$(sed -n 's/^name:[[:space:]]*//p' "$f" | head -1)"
    desc="$(sed -n 's/^description:[[:space:]]*//p' "$f" | head -1 | cut -c1-100)"
    printf '%-32s %s\n' "${name:-$rel}" "${desc:-}"
done
