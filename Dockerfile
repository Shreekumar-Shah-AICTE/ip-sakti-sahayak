# Stage 1: build the web bundle
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --silent
COPY web/ ./
RUN npm run build

# Stage 2: serve API + bundle from one port, keyless by default
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ api/
COPY corpus/ corpus/
COPY rules/ rules/
COPY ledger/ ledger/
COPY --from=web /web/dist web/dist
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
