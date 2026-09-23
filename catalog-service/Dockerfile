FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home app && mkdir /data && chown app:app /data
COPY catalog-service/ /app/
USER app
EXPOSE 8001
CMD ["uvicorn", "catalog.api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
