# Pinned by digest, as Nginx is: a rebuilt tag reaches the server only through a
# Dependabot pull request that CI has checked
FROM python:3.14.10-slim@sha256:3cabfd7d7aaf394e6040e79fa1eec6ca1c52b74ed9188650472695d9a9326999

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG APP=/app
ARG APPUSER=appuser

WORKDIR ${APP}

RUN addgroup --system ${APPUSER} && adduser --system --group ${APPUSER}

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY static/ static/

USER ${APPUSER}

EXPOSE 8000

# '*' is safe: only Nginx reaches port 8000, and it overwrites X-Forwarded-For
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
