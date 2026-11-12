FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# OpenShift runs containers as an arbitrary, non-root UID whose primary
# group is always 0 -- without this, alerts.db can't be written to /app
# when running under an OpenShift restricted SCC (e.g. Developer Sandbox;
# see infra/openshift/README.md). Harmless for local/Docker Compose use,
# where the container still just runs as root.
RUN chgrp -R 0 /app && chmod -R g=u /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
