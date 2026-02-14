# gemini-sidecar/Dockerfile
# Agent CLI sidecar - HTTP wrapper for Gemini + Claude Code CLIs with GitHub/GitLab auth
# Uses Node.js 22 (required by @google/gemini-cli)

FROM registry.access.redhat.com/ubi9/nodejs-22:latest

# Switch to root to install globally
USER 0

# Install git (for GitOps) and kubectl (for investigation)
RUN dnf install -y git && dnf clean all && \
    curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl && \
    kubectl version --client

# Install CLI tools: oc, argocd, kargo, tkn (all use latest/stable -- no pinned versions)
RUN \
    # oc -- OpenShift CLI (superset of kubectl, adds routes, projects, builds)
    curl -sL https://mirror.openshift.com/pub/openshift-v4/x86_64/clients/ocp/stable/openshift-client-linux.tar.gz \
      | tar -xz -C /usr/local/bin/ oc && \
    # argocd -- ArgoCD CLI (app sync status, diff, management)
    curl -sL https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64 \
      -o /usr/local/bin/argocd && chmod +x /usr/local/bin/argocd && \
    # kargo -- Kargo CLI (promotion stages, freight, warehouses)
    curl -sL https://github.com/akuity/kargo/releases/latest/download/kargo-linux-amd64 \
      -o /usr/local/bin/kargo && chmod +x /usr/local/bin/kargo && \
    # tkn -- Tekton CLI (pipelines, pipelineruns, taskruns)
    TKN_VERSION=$(curl -sL https://api.github.com/repos/tektoncd/cli/releases/latest \
      | grep '"tag_name"' | cut -d'"' -f4) && \
    curl -sL "https://github.com/tektoncd/cli/releases/download/${TKN_VERSION}/tkn_${TKN_VERSION#v}_Linux_x86_64.tar.gz" \
      | tar -xz -C /usr/local/bin/ tkn && \
    # helm -- Helm CLI (template --dry-run, lint, validate charts before pushing)
    curl -sL https://get.helm.sh/helm-$(curl -sL https://api.github.com/repos/helm/helm/releases/latest \
      | grep '"tag_name"' | cut -d'"' -f4)-linux-amd64.tar.gz \
      | tar -xz --strip-components=1 -C /usr/local/bin/ linux-amd64/helm && \
    # jq -- JSON processor (parsing kubectl output, API responses)
    curl -sL https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64 \
      -o /usr/local/bin/jq && chmod +x /usr/local/bin/jq && \
    # yq -- YAML processor (parsing/editing Helm values, K8s manifests)
    curl -sL https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
      -o /usr/local/bin/yq && chmod +x /usr/local/bin/yq && \
    # gh -- GitHub CLI (PR status, workflow runs, issue management)
    GH_VERSION=$(curl -sL https://api.github.com/repos/cli/cli/releases/latest \
      | grep '"tag_name"' | cut -d'"' -f4) && \
    curl -sL "https://github.com/cli/cli/releases/download/${GH_VERSION}/gh_${GH_VERSION#v}_linux_amd64.tar.gz" \
      -o /tmp/gh.tar.gz && tar -xzf /tmp/gh.tar.gz -C /tmp/ && \
    cp /tmp/gh_${GH_VERSION#v}_linux_amd64/bin/gh /usr/local/bin/gh && chmod +x /usr/local/bin/gh && \
    rm -rf /tmp/gh* && \
    # github-mcp-server -- GitHub MCP server (native PR/issue/action tools for Gemini + Claude CLIs)
    curl -sL https://github.com/github/github-mcp-server/releases/latest/download/github-mcp-server_Linux_x86_64.tar.gz \
      -o /tmp/mcp.tar.gz && tar -xzf /tmp/mcp.tar.gz -C /tmp/ && \
    cp /tmp/github-mcp-server /usr/local/bin/github-mcp-server && chmod +x /usr/local/bin/github-mcp-server && \
    rm -rf /tmp/mcp* /tmp/github-mcp-server* && \
    # glab -- GitLab CLI (MR status, pipeline runs, issue management)
    GLAB_VERSION=$(curl -sL https://gitlab.com/api/v4/projects/34675721/releases | \
      jq -r '.[0].tag_name') && \
    curl -sL "https://gitlab.com/gitlab-org/cli/-/releases/${GLAB_VERSION}/downloads/glab_${GLAB_VERSION#v}_Linux_x86_64.tar.gz" \
      -o /tmp/glab.tar.gz && tar -xzf /tmp/glab.tar.gz -C /tmp/ && \
    cp /tmp/bin/glab /usr/local/bin/glab && chmod +x /usr/local/bin/glab && \
    rm -rf /tmp/glab* /tmp/bin && \
    # Verify all CLIs installed
    oc version --client && argocd version --client && kargo version && tkn version && \
    helm version --short && jq --version && yq --version && \
    gh --version && github-mcp-server --help | head -1 && \
    glab --version

# Install Gemini CLI globally and symlink to /usr/local/bin for non-root PATH
# UBI9 Node.js puts global bins in /opt/app-root/src/.npm-global/bin/
RUN npm install -g @google/gemini-cli@latest && \
    ln -sf "$(npm prefix -g)/bin/gemini" /usr/local/bin/gemini && \
    /usr/local/bin/gemini --version || echo "Gemini CLI linked"

# Install GitLab MCP server (MR/issue/repo tools for Gemini + Claude CLIs)
RUN npm install -g @modelcontextprotocol/server-gitlab@latest && \
    ln -sf "$(npm prefix -g)/bin/gitlab-mcp-server" /usr/local/bin/gitlab-mcp-server && \
    /usr/local/bin/gitlab-mcp-server --help 2>&1 | head -1 || echo "GitLab MCP server linked"

# Install Claude Code CLI (for agents using Claude models via Vertex AI)
RUN npm install -g @anthropic-ai/claude-code@latest && \
    ln -sf "$(npm prefix -g)/bin/claude" /usr/local/bin/claude && \
    /usr/local/bin/claude --version || echo "Claude CLI linked"

# Install Python 3.12 + pip + test tools (QE agent needs pytest/httpx)
# Also install Chromium deps for Playwright headless browser testing
RUN dnf install -y \
    python3.12 python3.12-pip \
    nss atk at-spi2-atk cups-libs libdrm libXcomposite libXdamage \
    libXrandr mesa-libgbm pango alsa-lib libxkbcommon \
    && dnf clean all && \
    ln -sf /usr/bin/python3.12 /usr/local/bin/python3 && \
    python3 -m pip install pytest httpx && \
    python3 --version && python3 -m pytest --version && \
    npm install -g playwright@latest && \
    npx playwright install chromium && \
    npx playwright --version

# Create app directory
WORKDIR /app

# Copy package.json and install dependencies (jsonwebtoken for GitHub App auth)
COPY package.json .
RUN npm install --omit=dev

# Copy server code
COPY server.js .

# Create CLI config directories (rules come from ConfigMap mount)
RUN mkdir -p /home/default/.gemini && \
    mkdir -p /home/default/.claude

# Create non-root user directories
RUN mkdir -p /home/default /data/gitops && \
    chown -R 1001:0 /home/default /app /data && \
    chmod -R g=u /home/default /app /data

# Switch to non-root user
USER 1001
ENV HOME=/home/default

# Expose sidecar port
EXPOSE 9090

# Run the HTTP wrapper server
CMD ["node", "server.js"]
