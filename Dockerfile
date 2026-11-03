FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/data/hf_cache

WORKDIR /app

# CPU-only PyTorch for the sentence-transformers embeddings, in its own layer: it is large
# and rarely changes, and the default wheel would pull GPU libraries this project never uses
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies first so code changes don't invalidate this layer
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev,notebooks,nlp]"

COPY . .

CMD ["python", "-m", "src.pipeline"]
