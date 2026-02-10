FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .
COPY nwl_model.py .
COPY config/ config/
COPY assets/ assets/
COPY .streamlit/ .streamlit/

EXPOSE 8502

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8502/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8502", \
    "--server.headless=true", \
    "--server.enableXsrfProtection=true", \
    "--server.enableCORS=false", \
    "--browser.gatherUsageStats=false"]
