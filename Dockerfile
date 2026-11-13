# Pinned by digest, as Nginx is: a rebuilt tag reaches the server only through a
# Dependabot pull request that CI has checked
FROM python:3.15.2-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

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
