FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install NLTK data
RUN python -m pip install --no-cache-dir nltk && \
    python -m nltk.downloader punkt stopwords && \
    python -m nltk.downloader averaged_perceptron_tagger

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create uploads directory
RUN mkdir -p uploads && chmod 755 uploads

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["python", "app.py"]