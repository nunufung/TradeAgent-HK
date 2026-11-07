FROM python:3.14.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'free-claude-code @ git+https://github.com/Alishahryar1/free-claude-code.git@65d9f29788392d6e9948bfdee6519a44b1ceaad3'
RUN useradd -m -u 1000 app
WORKDIR /app
COPY --chown=app:app gateway.py /app/gateway.py
USER app
ENV HOME=/home/app PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["uvicorn", "gateway:create_app", "--factory", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--no-access-log"]
