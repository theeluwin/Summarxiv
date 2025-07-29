FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .
RUN uv sync --locked

EXPOSE 587
CMD ["uv", "run", "summarxiv.py"]
