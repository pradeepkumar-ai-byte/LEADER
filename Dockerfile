FROM python:3.12-slim

LABEL maintainer="Krish <pradeepkumar.ai.byte@gmail.com>"
LABEL description="Leader — credential-aware multi-backend AI agent router"

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e "." 2>/dev/null || \
    pip install --no-cache-dir aiohttp pyyaml rich

# Copy application code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Create config directory
RUN mkdir -p /root/.leader

# Expose the API server port
EXPOSE 8585

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8585/api/health')" || exit 1

# Default: run the API server
CMD ["leader", "serve", "--host", "0.0.0.0", "--port", "8585"]
