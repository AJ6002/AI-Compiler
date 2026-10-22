FROM python:3.12-slim

# Create non-root user
RUN groupadd -r steward && useradd -r -g steward steward

WORKDIR /app

# Install openpyxl and dependencies
RUN pip install --no-cache-dir openpyxl>=3.1.5

# Copy exploration script
COPY tools/exploration/explore.py /app/explore.py

USER steward

ENTRYPOINT ["python", "/app/explore.py"]
CMD ["--help"]
