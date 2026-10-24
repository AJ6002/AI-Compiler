# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime dependencies for compilation inspection (matching host compiler)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        openpyxl>=3.1.5 \
        pyarrow>=26.0.0 \
        python-calamine>=0.3.0 \
        pydantic>=2.9.0

# Create non-root user matching uid:gid 1000:1000
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g sandbox -m -s /bin/bash sandbox

# Create mount point directories with safe permissions
RUN mkdir -p /input /output /work && \
    chown -R sandbox:sandbox /input /output /work

USER sandbox
WORKDIR /work

CMD ["python", "/input/run_agent.py"]
