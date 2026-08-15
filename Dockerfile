FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN pip install --no-cache-dir .

ENV SECRETARY_DATA=/data
ENV SECRETARY_PORT=8080
EXPOSE 8080

CMD ["sales-secretary", "serve"]
