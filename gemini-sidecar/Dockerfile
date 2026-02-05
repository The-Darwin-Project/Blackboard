# gemini-sidecar/Dockerfile
# Gemini CLI sidecar - HTTP wrapper for gemini-cli with GitHub App auth
# Uses Node.js 22 (required by @google/gemini-cli)

FROM registry.access.redhat.com/ubi9/nodejs-22:latest

# Switch to root to install globally
USER 0

# Install Gemini CLI globally, git (for GitOps), and kubectl (for investigation)
RUN dnf install -y git kubernetes-client && dnf clean all && \
    npm install -g @google/gemini-cli@latest && \
    gemini --version || echo "Gemini CLI installed"

# Create app directory
WORKDIR /app

# Copy package.json and install dependencies (jsonwebtoken for GitHub App auth)
COPY package.json .
RUN npm install --omit=dev

# Copy server code
COPY server.js .

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
