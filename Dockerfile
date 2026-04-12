FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main

# Copy source
COPY . .
RUN poetry install --only main

EXPOSE 8501

CMD ["poetry", "run", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
