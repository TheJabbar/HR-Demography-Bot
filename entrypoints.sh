#!/usr/bin/sh

echo "Copying data from MinIO ..."
mc alias set stage ${MINIO_ENDPOINT} ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
mc cp -r stage/${MINIO_BUCKET}/${MINIO_PREFIX} /app/data/
echo "Copying data done ..."

echo "Starting HCM Insight Dashboard"
/app/.venv/bin/uvicorn main:app --port 7799 --host 0.0.0.0 --workers 1
