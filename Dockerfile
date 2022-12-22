FROM python:3.11
RUN pip install poetry
WORKDIR /bot
COPY poetry.lock pyproject.toml /bot/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root
COPY . /bot
EXPOSE 8000
CMD ["gunicorn", "--bind", ":8000", "app:app"]