FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY agent.py calendar_client.py ./

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

CMD ["uv", "run", "--no-dev", "agent.py", "start"]
