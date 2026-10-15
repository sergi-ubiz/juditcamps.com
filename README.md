# juditcamps.com

Web professional de **Judit Camps**, dietista-nutricionista a Taradell (Osona).

Lloc estàtic (HTML + CSS + JS vanilla), sense dependències de build: ràpid,
segur i fàcil de desplegar a qualsevol hosting estàtic (GitHub Pages, Netlify,
Cloudflare Pages…).

## Estructura

```
index.html          Pàgina principal (filosofia, qui sóc, serveis, mètode, contacte)
avis-legal.html     Avís legal
privadesa.html      Política de privadesa (RGPD)
cookies.html        Política de cookies
css/style.css       Estils (paleta taupe/menta, Quicksand + Inter)
js/main.js          Menú, formulari, consentiment GA4 i analítica pròpia
assets/             Logos, imatges, fonts i favicon
robots.txt          Obert a cercadors i crawlers d'IA (GPTBot, ClaudeBot…)
llms.txt            Resum del lloc per a assistents d'IA
sitemap.xml         Mapa del lloc
_headers            Capçaleres de seguretat (Netlify/Cloudflare Pages)
```

## Execució en local

No cal cap build. El backend serveix també la web i permet provar el formulari:

```bash
pip install -r requirements.txt
python3 app.py
# http://127.0.0.1:8080
```

En local s'usen les claus de prova de Cloudflare Turnstile (sempre validen) i,
si no hi ha `SMTP_USER`/`SMTP_PASSWORD`, el correu es mostra per consola en lloc
d'enviar-se. Amb `python3 -m http.server` el formulari no funciona (no hi ha
`/api/contact`).

## Analítica

El web combina Google Analytics 4 (només amb consentiment) i una mesura pròpia
separada, implementada al mòdul `analytics/`:

- Google Analytics 4: propietat «Judit Camps» d'Ultrabiz, només es carrega quan
  la persona accepta les cookies d'analítica. Identificador `G-B6JZRML5Q7`.
  La preferència es pot canviar al peu del web. No s'activa publicitat ni
  personalització d'anuncis.
- La mesura pròpia envia a `POST /api/pulse` les visites, el temps actiu, el
  desplaçament i les conversions. Respecta Global Privacy Control i no fa servir
  cookies d'analítica.

- El servidor geolocalitza la IP amb la base local DB-IP City Lite
  (`scripts/download_geoip.py`, s'inclou a la imatge) i la descarta; el visitant
  s'identifica amb un hash anònim que rota cada dia.
- Persistència del mòdul propi: Firestore quan es configura
  (`ANALYTICS_BACKEND=firestore`), SQLite en local (`analytics-local.sqlite3`).
  Firestore encara s'ha de configurar per conservar aquestes dades a Cloud Run;
  GA4 guarda les seves dades a la propietat d'Ultrabiz i no depèn de Firestore.
- **Tauler privat**: `https://juditcamps.com/stats/<STATS_TOKEN>/` (sense token
  configurat respon 404). KPI amb comparació amb el període anterior, evolució,
  canals, fonts, pàgines, ubicació, dispositius, campanyes UTM, mapa de calor i
  exportació CSV. Clicant qualsevol fila es filtra tot el tauler.

Variables d'entorn:

| Variable | Ús |
|----------|----|
| `STATS_TOKEN` | Secret de l'enllaç privat del tauler (≥ 32 caràcters aleatoris) |
| `ANALYTICS_SALT` | Secret del hash anònim de visitant |
| `ANALYTICS_BACKEND` | `firestore` (producció) o `sqlite` (local, per defecte) |
| `ANALYTICS_FIRESTORE_DB` | Base de dades Firestore (per defecte `juditcamps`) |

En local: `STATS_TOKEN=prova123 python3 app.py` i obrir
`http://127.0.0.1:8080/stats/prova123/`. Proves: `python -m pytest tests`.

Per etiquetar campanyes: `https://juditcamps.com/?utm_source=instagram&utm_medium=social&utm_campaign=nom`
(o `utm_medium=qr` per a fulletons i targetes).

## Pendents de configuració

- Formulari: configurar les credencials SMTP de Google Workspace perquè pugui
  enviar correus.
- Mesura pròpia: configurar Firestore i els secrets `STATS_TOKEN` i
  `ANALYTICS_SALT` per conservar dades i activar el tauler privat. Google
  Analytics funciona per separat i no necessita Firestore.

## Seguretat

- Content-Security-Policy estricta (meta + `nginx.conf`), incloent els dominis
  necessaris per a GA4.
- Formulari amb captcha (Turnstile), honeypot anti-spam, validació i consentiment RGPD.
- Cookies GA4 només amb consentiment; pàgines legals RGPD/cookies en català i
  castellà.
- Les dependències de tercers s'afegeixen només després del consentiment o quan
  s'interactua amb el formulari (GA4 o Turnstile).

## Visibilitat en IA (AI SEO)

- `llms.txt` amb el resum del negoci per a LLMs.
- `robots.txt` permet explícitament GPTBot, OAI-SearchBot, ClaudeBot,
  PerplexityBot, Google-Extended i altres.
- JSON-LD schema.org (`MedicalBusiness` + `Person`) a `index.html`.
