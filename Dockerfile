FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --locked

EXPOSE 587
CMD ["uv", "run", "entry.py", "--config", "config.yaml", "--prompt", "templates/prompt.txt"]
