#!/usr/bin/env bash
# Build the demo page: real maps of Sentry (4 repositories) and Open edX (4 repositories), with every HTTP link
# between their services provable down to the line. Writes dist/demo/index.html (one self-contained file).
#
#   tools/demo/build.sh                 every step
#   STEPS="spec page" tools/demo/build.sh   only some: links graphify spec page
#
# Needs (see docs/DEMO.md):
#   REPOS        folder with sentry/ relay/ snuba/ symbolicator/ and openedx/{openedx-platform,course-discovery,
#                credentials,frontend-app-learning}/, checked out at the answer keys' commits
#   PY           a Python with atlas-bridge[links] installed (default: python3)
#   GRAPHIFY_PY  the Python Graphify is installed in (default: the one `graphify` runs with)
#   SCIP_SENTRY, SCIP_OPENEDX  folders of <repo>.scip indexes (optional; without them no link is "Confirmed by SCIP")
#   WORK         scratch folder (default: .demo-work, git-ignored)
#   GRAPHIFY_ONLY  map only these repositories again (space-separated), e.g. GRAPHIFY_ONLY=sentry
set -euo pipefail
cd "$(dirname "$0")/../.."
ATLAS=$PWD
REPOS=${REPOS:?set REPOS to the folder holding the checked-out repositories}
PY=${PY:-python3}
GRAPHIFY_PY=${GRAPHIFY_PY:-$(head -1 "$(command -v graphify)" | sed 's/^#!//')}
WORK=${WORK:-$ATLAS/.demo-work}
STEPS=${STEPS:-links graphify spec page}
mkdir -p "$WORK/mirror" dist/demo

SENTRY=(sentry relay snuba symbolicator)
OPENEDX=(openedx-platform course-discovery credentials frontend-app-learning)
folder() { case $1 in sentry | relay | snuba | symbolicator) echo "$REPOS/$1" ;; *) echo "$REPOS/openedx/$1" ;; esac; }
# production source only: what the map shows (tests, fixtures and migrations would bury the services)
sources() {
  case $1 in
    sentry) echo 'src/*.py' ;; # plus the frontend files that call the API, added in graphify_step
    relay) echo '*.rs' ;;
    snuba) echo 'snuba/*.py rust_snuba/*.rs' ;;
    symbolicator) echo 'crates/*.rs' ;;
    openedx-platform) echo 'lms/*.py cms/*.py openedx/*.py common/*.py xmodule/*.py' ;;
    course-discovery) echo 'course_discovery/*.py' ;;
    credentials) echo 'credentials/*.py' ;;
    frontend-app-learning) echo 'src/*.js src/*.jsx src/*.ts src/*.tsx' ;;
  esac
}
NOT_PRODUCTION='(^|/)(tests?|testutils|test_utils|fixtures|__tests__|testing|benches|examples|migrations)/|(^|/)test_[^/]*\.py$|_tests?\.py$|\.(test|spec)\.[jt]sx?$|conftest\.py$'

graphify_step() {
  for repo in ${GRAPHIFY_ONLY:-${SENTRY[*]} ${OPENEDX[*]}}; do
    local src m=$WORK/mirror/$repo
    src=$(folder "$repo")
    rm -rf "$m" && mkdir -p "$m"
    # shellcheck disable=SC2046
    git -C "$src" ls-files -- $(sources "$repo") | grep -Ev "$NOT_PRODUCTION" > "$m.files"
    # Sentry's frontend is 10,000 files; only those that call its own API (the --within links) go on the map
    [[ $repo == sentry ]] && python3 -c 'import json,sys; print("\n".join(sorted({l["call"]["file"] for l in json.load(open(sys.argv[1]))["links"]})))' \
      "$WORK/sentry-within.json" >> "$m.files"
    rsync -a --files-from="$m.files" "$src/" "$m/"
    (cd "$m" && GRAPHIFY_NO_TIPS=1 "$GRAPHIFY_PY" "$ATLAS/tools/demo/graphify_ast.py" > "$m.log" 2>&1) ||
      { tail -5 "$m.log"; exit 1; }
    echo "graphify  $repo: $(wc -l < "$m.files" | tr -d ' ') files"
  done
}

links_step() {
  local scip_s=() scip_o=()
  [[ -n ${SCIP_SENTRY:-} ]] && scip_s=(--scip-dir "$SCIP_SENTRY")
  [[ -n ${SCIP_OPENEDX:-} ]] && scip_o=(--scip-dir "$SCIP_OPENEDX")
  (cd bridge && "$PY" -m atlas_bridge links $(for r in "${SENTRY[@]}"; do echo "$r=$(folder "$r")"; done) \
    --alias upstream=sentry ${scip_s[@]+"${scip_s[@]}"} -o "$WORK/sentry-links.json")
  (cd bridge && "$PY" -m atlas_bridge links $(for r in "${OPENEDX[@]}"; do echo "$r=$(folder "$r")"; done) \
    --alias lms=openedx-platform --alias studio=openedx-platform --alias catalog=course-discovery \
    --alias discovery=course-discovery --alias credentials=credentials ${scip_o[@]+"${scip_o[@]}"} -o "$WORK/openedx-links.json")
  # Sentry's frontend calling its own API: shown on the map, but no answer key covers it, so it is not scored
  (cd bridge && "$PY" -m atlas_bridge links "sentry=$(folder sentry)" --within -o "$WORK/sentry-within-all.json")
  python3 tools/demo/within.py "$WORK/sentry-within-all.json" > "$WORK/sentry-within.json"
  # each key judges its own protocol: the HTTP keys the HTTP links, Sentry's Kafka key the Kafka links
  for key in sentry openedx; do python3 tools/demo/protocol.py http "$WORK/$key-links.json" > "$WORK/$key-http.json"; done
  python3 tools/demo/protocol.py kafka "$WORK/sentry-links.json" > "$WORK/sentry-kafka.json"
  python3 eval/score.py eval/sentry/answer-key.json "$WORK/sentry-http.json" > "$WORK/sentry-score.txt"
  python3 eval/score.py eval/openedx/answer-key.json "$WORK/openedx-http.json" > "$WORK/openedx-score.txt"
  python3 eval/tiny/score.py eval/sentry/kafka-key.json "$WORK/sentry-kafka.json" --json > "$WORK/sentry-kafka-score.json"
  echo "score     sentry kafka $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["summary"])' "$WORK/sentry-kafka-score.json")"
  echo "score     sentry  $(tail -1 "$WORK/sentry-score.txt")"
  echo "score     openedx $(tail -1 "$WORK/openedx-score.txt")"
}

spec_one() { # key title repos...
  local key=$1 title=$2 graphs=() folders=() more=() r
  shift 2
  [[ -f $WORK/$key-within.json ]] && more=(--links "$WORK/$key-within.json")
  for r in "$@"; do
    graphs+=("$r=$WORK/mirror/$r/graphify-out/graph.json")
    folders+=(--repo "$r=$(folder "$r")")
  done
  local kafka=() # the channel key's score, where there is one
  [[ -f $WORK/$key-kafka-score.json ]] && kafka=("$WORK/$key-kafka-score.json")
  python3 tools/demo/accuracy.py "$WORK/$key-score.txt" "tools/demo/$key.json" ${kafka[@]+"${kafka[@]}"} > "$WORK/$key-accuracy.json"
  (cd bridge && "$PY" -m atlas_bridge spec "${graphs[@]}" --title "$title" "${folders[@]}" \
    --links "$WORK/$key-links.json" ${more[@]+"${more[@]}"} --accuracy "$WORK/$key-accuracy.json" -o "$WORK/$key-spec.json")
}

spec_step() {
  spec_one sentry 'Sentry, mapped by Graphify' "${SENTRY[@]}"
  spec_one openedx 'Open edX, mapped by Graphify' "${OPENEDX[@]}"
}

page_step() {
  node scripts/build.mjs --offline --maps="sentry:$WORK/sentry-spec.json:Sentry,openedx:$WORK/openedx-spec.json:Open edX" \
    --out=dist/demo/index.html
}

for step in $STEPS; do "${step}_step"; done
