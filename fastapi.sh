# fastapi.sh
/home/nur_fajarsa/wikisaas_backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile /etc/letsencrypt/live/kowan.nurfajar.tech/privkey.pem \
  --ssl-certfile /etc/letsencrypt/live/kowan.nurfajar.tech/fullchain.pem
