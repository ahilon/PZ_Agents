# Deployment na serwerze — Docker

Instrukcja uruchamiania projektu na VPS/serwerze za pomocą Dockera.

---

## Wymagania wstępne

Na serwerze musi być zainstalowane:
- Docker (≥ 24.0)
- Docker Compose (≥ 2.20) — wbudowany w nowsze wersje jako `docker compose`
- Git

Sprawdź:
```bash
docker --version
docker compose version
```

---

## 1. Instalacja Dockera na serwerze (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker          # zastosuj grupę bez wylogowania
```

---

## 2. Sklonuj repo na serwer

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
```

Lub jeśli repo jest prywatne — użyj deploy key lub PAT:
```bash
git clone https://TWOJ_TOKEN@github.com/OWNER/REPO.git
```

---

## 3. Skonfiguruj zmienne środowiskowe

```bash
cp .env.example .env
nano .env          # uzupełnij OPENAI_API_KEY, GIT_BOT_TOKEN itp.
```

`.env` nigdy nie trafia do repo (jest w `.gitignore`).

---

## 4. Zbuduj i uruchom

```bash
# Zbuduj obraz i wystartuj w tle
docker compose up --build -d

# Sprawdź czy działa
docker compose ps
docker compose logs -f app
```

Aplikacja dostępna pod: `http://IP_SERWERA:8501`

---

## 5. Komendy codzienne

```bash
# Restart aplikacji
docker compose restart app

# Zatrzymanie
docker compose down

# Rebuild po zmianach w kodzie
docker compose up --build -d

# Podgląd logów na żywo
docker compose logs -f

# Wejdź do kontenera (debugging)
docker compose exec app bash
```

---

## 6. Aktualizacja kodu (deploy)

```bash
git pull origin main
docker compose up --build -d
```

Lub jeśli używasz wolumenu z kodem (jak w `docker-compose.yml` powyżej):
```bash
git pull origin main
docker compose restart app    # wystarczy restart, bez rebuild
```

---

## 7. Nginx jako reverse proxy (opcjonalne)

Jeśli chcesz dostęp przez port 80/443 zamiast 8501:

```bash
sudo apt install nginx
```

Konfiguracja `/etc/nginx/sites-available/agents`:
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
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/agents /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS przez Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d twoja-domena.com
```

---

## 8. Różne frameworki UI — zmiana portu

Edytuj `docker-compose.yml` i `Dockerfile` w zależności od frameworka:

| Framework  | Port | CMD w Dockerfile |
|------------|------|-----------------|
| Streamlit  | 8501 | `streamlit run app.py --server.address=0.0.0.0 --server.port=8501` |
| FastAPI    | 8000 | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Gradio     | 7860 | `python app.py` (Gradio domyślnie 7860) |

---

## 9. Checklist — nowy serwer

```
[ ] Docker + Docker Compose zainstalowane
[ ] Repo sklonowane
[ ] .env uzupełniony (OPENAI_API_KEY minimum)
[ ] docker compose up --build -d uruchomiony
[ ] Aplikacja dostępna pod http://IP:PORT
[ ] (opcjonalnie) Nginx skonfigurowany
[ ] (opcjonalnie) HTTPS przez certbot
[ ] (opcjonalnie) docker compose down/up dodane do crontab lub systemd
```

---

## 10. Automatyczny restart po restarcie serwera

`restart: unless-stopped` w `docker-compose.yml` wystarczy — kontener wstaje sam po restarcie systemu, o ile Docker jest skonfigurowany jako serwis systemd (domyślnie po instalacji przez `get.docker.com`).

Sprawdź:
```bash
sudo systemctl is-enabled docker    # powinno zwrócić "enabled"
```
