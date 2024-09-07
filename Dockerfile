FROM python:3.12.5 AS builder

WORKDIR /app

RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.8.0 python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

FROM python:3.12.5-slim-bullseye

WORKDIR /app

COPY --from=builder /usr/local/bin/poetry /usr/local/bin/
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /app /app

RUN rm -rf /var/cache/apt/* /root/.cache/pip/

COPY . .

ENV PYTHONPATH="/app:$PYTHONPATH"

ENTRYPOINT ["python"]

CMD ["marketing_budget_tennisi_bot/main.py"]