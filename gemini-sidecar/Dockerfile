# gemini-sidecar/Dockerfile
# Agent CLI sidecar - HTTP wrapper for Gemini + Claude Code CLIs with GitHub App auth
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
    # Verify all CLIs installed
    oc version --client && argocd version --client && kargo version && tkn version && \
    helm version --short && jq --version && yq --version

# Install Gemini CLI globally and symlink to /usr/local/bin for non-root PATH
# UBI9 Node.js puts global bins in /opt/app-root/src/.npm-global/bin/
RUN npm install -g @google/gemini-cli@latest && \
    ln -sf "$(npm prefix -g)/bin/gemini" /usr/local/bin/gemini && \
    /usr/local/bin/gemini --version || echo "Gemini CLI linked"

# Install Claude Code CLI (for agents using Claude models via Vertex AI)
RUN npm install -g @anthropic-ai/claude-code@latest && \
    ln -sf "$(npm prefix -g)/bin/claude" /usr/local/bin/claude && \
    /usr/local/bin/claude --version || echo "Claude CLI linked"

# Install Playwright + Chromium for headless browser testing (QE agent)
RUN npm install -g playwright@latest && \
    npx playwright install --with-deps chromium && \
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
