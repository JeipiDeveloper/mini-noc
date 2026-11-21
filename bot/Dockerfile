FROM python:3.12-alpine

WORKDIR /app
COPY triage_bot.py .

ENV PORT=8080 \
    DATA_DIR=/data

RUN mkdir -p /data

EXPOSE 8080

CMD ["python", "triage_bot.py"]
