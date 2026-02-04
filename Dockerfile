FROM registry.access.redhat.com/ubi9/ubi:latest
USER 0
# Install Runtimes (Latest Stable via DNF)
RUN dnf install -y python3 python3-pip git nodejs npm && dnf clean all
# Install Gemini CLI (Latest)
RUN npm install -g @google/gemini-cli@latest
USER 1001
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY src src
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
