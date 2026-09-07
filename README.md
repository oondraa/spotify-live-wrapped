# Spotify Live Wrapped

Vlastní "24/7 Spotify Wrapped" – na pozadí průběžně sbírá tvou historii
poslechu přes Spotify Web API a zobrazuje ji jako živý statistický
dashboard (top interpreti, skladby, alba, grafy aktivity, listening
streak, night owl score a další).

Skládá se ze dvou nezávislých procesů:

- **collector** (`app/collector.py`) – na pozadí každých pár minut
  stahuje nedávno přehrané skladby a ukládá je do SQLite databáze.
- **web** (`app/web.py`) – Flask aplikace s přihlášením, která z
  databáze počítá statistiky a zobrazuje dashboard.

## Rychlý start (lokálně)

Vyžaduje Python 3.10+ a [Spotify Developer](https://developer.spotify.com/dashboard)
aplikaci (Client ID + Client Secret, Redirect URI nastavené na
`http://127.0.0.1:8080` nebo vlastní).

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# doplň SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET / SPOTIFY_REDIRECT_URI,
# ADMIN_USERNAME / ADMIN_PASSWORD a FLASK_SECRET_KEY v .env

python scripts/authorize.py      # jednorázová autorizace Spotify účtu
python app/collector.py          # v jednom terminálu – sběr dat
python app/web.py                # ve druhém terminálu – dashboard na http://localhost:5000
```

## Nasazení na Linux server

V repu je instalátor, který založí virtuální prostředí, nechá tě
zadat API klíče a přihlašovací údaje (rovnou je zapíše do `.env`,
nic se necommitne), provede autorizaci Spotify účtu a volitelně
nainstaluje obě služby jako systemd jednotky.

```bash
git clone <url-tohoto-repa> spotify-live-wrapped
cd spotify-live-wrapped
bash deploy/install.sh
```

Instalátor se postupně zeptá na:

1. Spotify `CLIENT_ID` / `CLIENT_SECRET` / `REDIRECT_URI`
2. Přihlašovací jméno a heslo do webového dashboardu (`FLASK_SECRET_KEY`
   se vygeneruje automaticky)
3. Jestli chceš rovnou provést autorizaci Spotify účtu (vypíše odkaz,
   ty ho otevřeš v prohlížeči, přihlásíš se a vrátíš zpět přesměrovanou
   URL – token se pak už obnovuje sám)
4. Jestli chceš nainstalovat systemd služby `spotify-collector` a
   `spotify-web` (běh na pozadí + start po rebootu)

Šablony jednotek jsou v `deploy/systemd/`. Web běží přes `gunicorn`
(viz `requirements.txt`), collector jako obyčejný Python proces.

Užitečné příkazy po instalaci:

```bash
sudo systemctl status spotify-web spotify-collector
sudo journalctl -u spotify-web -f
sudo journalctl -u spotify-collector -f
```

Pokud web hlásí "Aplikace ještě není nakonfigurovaná", chybí něco
v `.env` – doplň to a `sudo systemctl restart spotify-web`.

## Konfigurace (.env)

Viz `.env.example` pro kompletní seznam proměnných. Nic z toho se
necommituje – `.env`, `data/` (databáze + token cache) i `.venv/`
jsou v `.gitignore`.

| Proměnná | Popis |
|---|---|
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` | API klíče ze Spotify Developer Dashboardu |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | přihlášení do web dashboardu |
| `FLASK_SECRET_KEY` | podpis Flask session cookie – náhodný hex řetězec |
| `APP_TITLE` | název zobrazený v UI (výchozí "Spotify Live Wrapped") |
| `WEB_HOST`, `WEB_PORT` | na čem poslouchá web (výchozí `0.0.0.0:5000`) |
| `COLLECT_INTERVAL_SECONDS` | jak často collector stahuje nová data (výchozí 600 s) |
| `DATA_DIR` | kam se ukládá `spotify_history.db` a `.cache` (výchozí `./data`) |

## Bezpečnostní poznámky

- Žádné API klíče ani hesla nejsou v kódu – všechno jde přes `.env`.
- `data/` obsahuje tvoji osobní historii poslechu a OAuth token –
  nikdy to necommituj a nesdílej.
- Dashboard je chráněný jménem/heslem, ale doporučuje se pouštět ho
  za reverzní proxy s HTTPS (nginx/caddy), pokud běží na veřejné IP.

## Licence

[PolyForm Noncommercial License 1.0.0](LICENSE) – použití pro osobní,
nekomerční účely je v pořádku (studium, vlastní hobby nasazení,
úpravy pro sebe). Komerční využití vyžaduje svolení autora.
