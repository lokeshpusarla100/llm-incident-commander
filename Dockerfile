FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
# gcc and python3-dev might be needed for some packages, preventing potential install errors.
# We keep it minimal but functional.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser

# Copy application code
COPY app ./app
COPY templates ./templates
COPY static ./static

# Change ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (Cloud Run typically expects 8080)
EXPOSE 8080

# Start the application
# Using --workers 1 as requested for Cloud Run horizontal scaling
# Binding to 0.0.0.0:8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
