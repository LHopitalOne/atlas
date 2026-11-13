#!/usr/bin/env bash
# Build every answer key's code with Graphify (code only, no LLM), as a user would run it: each repository of a
# multi-repository project on its own, then `graphify merge-graphs`; each single-repository project as one corpus.
#
# Usage: eval/graphify-baseline/build.sh <work folder> <python with graphifyy installed>
#   REPOS  the folder eval/README.md fetches the repositories into (required)
set -u
WORK=${1:?usage: build.sh <work folder> <python with graphifyy installed>}; PY=${2:?python}
: "${REPOS:?set REPOS to the folder eval/README.md fetches the repositories into}"
GFY=$(dirname "$PY")/graphify; HERE=$(cd "$(dirname "$0")" && pwd); A=$(cd "$HERE/../.." && pwd)
C=$WORK/corpus; mkdir -p "$C"

build() {  # build <folder>: Graphify's graph of that folder, into <folder>/graphify-out/graph.json
  local t0=$SECONDS
  (cd "$1" && GRAPHIFY_NO_TIPS=1 "$PY" "$HERE/build_ast.py" > "$1.log" 2>&1) || { echo "FAIL $1"; tail -3 "$1.log"; return; }
  echo "built $(basename "$1") in $((SECONDS - t0)) s"
}

copy() {  # copy <repository folder> <corpus folder>: the files git tracks, so Graphify writes nothing into the download
  rm -rf "${2:?}" && mkdir -p "$2"
  # regular files only: openedx-platform tracks symlinks into node_modules, which a fresh download does not have
  git -C "$1" ls-files -z --format='%(objectmode) %(path)' | perl -0 -ne 'print substr($_, 7) if /^100(644|755) /' |
    rsync -a --from0 --files-from=- "$1/" "$2/"
}

for r in sentry relay snuba symbolicator openedx-platform course-discovery credentials frontend-app-learning; do
  copy "$REPOS/$r" "$C/$r" && build "$C/$r"
done
for set in "sentry:sentry relay snuba symbolicator" "openedx:openedx-platform course-discovery credentials frontend-app-learning"; do
  name=${set%%:*}; args=()
  for r in ${set#*:}; do args+=("$C/$r/graphify-out/graph.json"); done
  GRAPHIFY_NO_TIPS=1 "$GFY" merge-graphs "${args[@]}" --out "$WORK/$name-merged.json" > "$WORK/$name-merge.log" 2>&1
  echo "merged $name: $(grep -i merged "$WORK/$name-merge.log" | tail -1)"
done

for p in immich plane zulip; do
  copy "$REPOS/$p" "$C/dev-$p" && build "$C/dev-$p"
done
for app in "$A"/eval/tiny/apps/* "$A"/eval/tiny/apps2/*; do
  [[ -f $app/TRUTH.json ]] || continue
  d="$C/$(basename "$(dirname "$app")")-$(basename "$app")"
  rsync -a --delete --exclude node_modules --exclude graphify-out "$app/" "$d/"
  build "$d"
done
echo done
