#!/usr/bin/env bash
# Regenerate generated/self-graph.json from the current source.
# Needs: Node deps (npm install), Python 3 with tree-sitter (pip install -r tools/index-self/requirements.txt),
# and the `scip` CLI (https://github.com/sourcegraph/scip/releases) on PATH or in $SCIP_BIN.
set -euo pipefail
cd "$(dirname "$0")/../.."
SCIP="${SCIP_BIN:-scip}"
npx scip-typescript index --output generated/index.scip >/dev/null
"$SCIP" print --json generated/index.scip > generated/index.scip.json 2>/dev/null
python3 tools/index-self/index_self.py . generated/index.scip.json generated/self-graph.json
rm -f generated/index.scip generated/index.scip.json
