# Postawienie serwera — Docker od zera

Instrukcja instalacji Dockera i uruchamiania projektu Python na świeżym serwerze VPS.

---

## 1. Wymagania wstępne

Świeży serwer Ubuntu 22.04 / 24.04 z dostępem SSH i użytkownikiem z `sudo`.

---

## 2. Instalacja Dockera

```bash
# Dodaj oficjalne repozytorium Docker
curl -fsSL https://get.docker.com | sh

# Dodaj swojego użytkownika do grupy docker (bez sudo)
sudo usermod -aG docker $USER
newgrp docker

# Sprawdź instalację
docker --version
docker compose version
```

---

## 3. Sklonuj repo na serwer

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
```

Jeśli repo prywatne — użyj PAT:
```bash
git clone https://TWOJ_TOKEN@github.com/OWNER/REPO.git
```

---

## 4. Skonfiguruj zmienne środowiskowe

```bash
cp .env.example .env
nano .env   # uzupełnij OPENAI_API_KEY i inne klucze
```

`.env` nigdy nie trafia do repo (jest w `.gitignore`).

---

## 5. Utwórz Dockerfile

W katalogu projektu utwórz `Dockerfile`:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main

COPY . .
RUN poetry install --only main

EXPOSE 8501
CMD ["poetry", "run", "streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
```

Zmień ostatnią linię `CMD` w zależności od frameworka:

| Framework | CMD |
|-----------|-----|
| Streamlit | `streamlit run app.py --server.address=0.0.0.0 --server.port=8501` |
| FastAPI   | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Gradio    | `python app.py` |

---

## 6. Utwórz docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"   # zmień port jeśli używasz FastAPI (8000) lub Gradio (7860)
    env_file:
      - .env
    volumes:
      - .:/app
      - /app/.venv
    restart: unless-stopped
```

---

## 7. Zbuduj i uruchom

```bash
docker compose up --build -d

# Sprawdź status
docker compose ps
docker compose logs -f app
```

Aplikacja dostępna pod: `http://IP_SERWERA:8501`

---

## 8. Komendy codzienne

```bash
docker compose restart app          # restart po zmianach w .env
docker compose up --build -d        # rebuild po zmianach w kodzie
docker compose down                 # zatrzymanie
docker compose logs -f              # logi na żywo
docker compose exec app bash        # wejście do kontenera
```

---

## 9. Aktualizacja kodu

```bash
git pull origin main
docker compose up --build -d
```

---

## 10. Nginx jako reverse proxy (port 80/443)

```bash
sudo apt install nginx
```

Plik `/etc/nginx/sites-available/app`:
```nginx
server {
    listen 80;
    server_name twoja-domena.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/app /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 11. HTTPS — Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d twoja-domena.com
```

Certbot automatycznie odświeża certyfikat co 90 dni.

---

## 12. Checklist

```
[ ] Docker zainstalowany (get.docker.com)
[ ] Użytkownik w grupie docker
[ ] Repo sklonowane
[ ] .env uzupełniony
[ ] Dockerfile utworzony
[ ] docker-compose.yml utworzony
[ ] docker compose up --build -d uruchomiony
[ ] Aplikacja dostępna pod http://IP:PORT
[ ] (opcjonalnie) Nginx skonfigurowany
[ ] (opcjonalnie) HTTPS przez certbot
```
