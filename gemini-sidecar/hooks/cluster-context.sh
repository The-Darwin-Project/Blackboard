#!/bin/bash
# gemini-sidecar/hooks/cluster-context.sh
# @ai-rules:
# 1. [Pattern]: Gemini SessionStart hook -- surfaces remote K8s cluster metadata as systemMessage.
# 2. [Pattern]: Reads from /config/remote-clusters/*.json (ConfigMap mount, rendered from Helm values).
# 3. [Constraint]: Exit 0 always -- hook failure must not block the agent's session.
# 4. [Constraint]: Empty output = no clusters configured = silent (no systemMessage injected).

META_DIR="/config/remote-clusters"
[ -d "$META_DIR" ] || exit 0

CONTEXT=""
for f in "$META_DIR"/*.json; do
  [ -f "$f" ] || continue
  CONTEXT+=$(node -e "
    const c = JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));
    let l = '- K8s_' + c.name + ': ' + (c.displayName || c.name) + ' (read-only MCP)';
    if (c.namespacePattern) l += '\\n  Namespace pattern: ' + c.namespacePattern;
    if (c.namespaces?.length) l += '\\n  Accessible namespaces: ' + c.namespaces.join(', ');
    process.stdout.write(l);
  " "$f")
  CONTEXT+=$'\n'
done

[ -z "$CONTEXT" ] && exit 0

node -e "
  process.stdout.write(JSON.stringify({
    decision: 'allow',
    systemMessage: 'Remote K8s Clusters:\\n' + process.argv[1] + '\\nUse resources_list with namespace param. namespaces_list and events_list may not work on multi-tenant clusters.'
  }));
" "$CONTEXT"
exit 0
