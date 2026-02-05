# BlackBoard/Dockerfile
# Darwin Blackboard (Brain) - Central nervous system
# Multi-stage build: React UI + Python FastAPI

# =============================================================================
# Stage 1: Build React UI
# =============================================================================
FROM registry.access.redhat.com/ubi9/nodejs-22:latest AS react-builder

WORKDIR /build

# Copy package files first for better layer caching
COPY ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy source and build
COPY ui/ ./
RUN npm run build && \
    # Validate build output exists
    test -f /build/dist/index.html || (echo "ERROR: React build failed - index.html not found" && exit 1)

# =============================================================================
# Stage 2: Python Application
# =============================================================================
FROM registry.access.redhat.com/ubi9/ubi:latest

# Install system packages as root
USER 0
RUN dnf install -y python3 python3-pip git nodejs npm && dnf clean all

# Install Gemini CLI (Latest) - required for SysAdmin agent
RUN npm install -g @google/gemini-cli@latest && \
    # Debug: show where npm installed global packages
    echo "npm global prefix: $(npm prefix -g)" && \
    ls -la "$(npm prefix -g)/bin/" | head -20 && \
    # Create symlink to /usr/local/bin (standard PATH location)
    ln -sf "$(npm prefix -g)/bin/gemini" /usr/local/bin/gemini && \
    # Verify binary exists
    test -x /usr/local/bin/gemini && echo "Gemini CLI installed at /usr/local/bin/gemini"

# Ensure /usr/local/bin is in PATH (usually already is, but be explicit)
ENV PATH="/usr/local/bin:${PATH}"

# Set up working directory
WORKDIR /app

# Install Python dependencies as root (before switching to non-root)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src src

# Copy built React UI from Stage 1
COPY --from=react-builder /build/dist /app/ui/dist

# Create non-root user home directory for OpenShift compatibility
RUN mkdir -p /home/appuser && chown -R 1001:0 /home/appuser /app
ENV HOME=/home/appuser

# Switch to non-root user (OpenShift SCC compliance)
USER 1001

# Expose port
EXPOSE 8000

# Run the FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
