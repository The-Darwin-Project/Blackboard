# BlackBoard/Dockerfile
# Darwin Blackboard (Brain) - Central nervous system
# Base: Red Hat UBI 9 (OpenShift compatible)

FROM registry.access.redhat.com/ubi9/ubi:latest

# Install system packages as root
USER 0
RUN dnf install -y python3 python3-pip git nodejs npm && dnf clean all

# Install Gemini CLI (Latest) - required for SysAdmin agent
RUN npm install -g @google/gemini-cli@latest

# Set up working directory
WORKDIR /app

# Install Python dependencies as root (before switching to non-root)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src src

# Create non-root user home directory for OpenShift compatibility
RUN mkdir -p /home/appuser && chown -R 1001:0 /home/appuser /app
ENV HOME=/home/appuser

# Switch to non-root user (OpenShift SCC compliance)
USER 1001

# Expose port
EXPOSE 8000

# Run the FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
