FROM python:3.11-slim

RUN pip install --no-cache-dir gdown scipy pillow boto3 tqdm

WORKDIR /app
COPY compcars_downloader.py /app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "compcars_downloader.py"]
