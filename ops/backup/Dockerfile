# pg_dump must be at least as recent as the server: use the same Postgres major (17).
FROM postgres:17-alpine
RUN apk add --no-cache python3 tzdata
COPY backup.py /usr/local/bin/kwak-backup.py
ENTRYPOINT ["python3", "/usr/local/bin/kwak-backup.py"]
