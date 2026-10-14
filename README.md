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
css/style.css       Estils (paleta verda/neutra, Cormorant Garamond + Inter)
js/main.js          Menú, animacions i enviament del formulari
assets/             Logo SVG, favicon
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

## Analítica d'audiències pròpia

Mesura de visites sense cookies ni serveis de tercers (mòdul `analytics/`):

- `js/main.js` envia a `POST /api/pulse` la visita, el temps actiu, el
  desplaçament i les conversions (formulari enviat). Respecta Global Privacy
  Control.
- El servidor geolocalitza la IP amb la base local DB-IP City Lite
  (`scripts/download_geoip.py`, s'inclou a la imatge) i la descarta; el visitant
  s'identifica amb un hash anònim que rota cada dia.
- Persistència: Firestore en producció (`ANALYTICS_BACKEND=firestore`), SQLite
  en local (`analytics-local.sqlite3`).
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

## Configuració pendent abans de publicar

1. **Formulari de contacte** — crear un formulari a [Formspree](https://formspree.io)
   i substituir `FORMSPREE_ID` a `index.html`.
2. **Captcha** — crear un widget a [Cloudflare Turnstile](https://www.cloudflare.com/products/turnstile/)
   per al domini `juditcamps.com` i substituir `TURNSTILE_SITE_KEY` a `index.html`.
   Activar la verificació del token Turnstile dins la configuració de Formspree.
3. **Imatge Open Graph** — afegir `assets/og-image.jpg` (1200×630) amb una foto
   professional de la Judit.

## Seguretat

- Content-Security-Policy estricta (meta + `_headers`).
- Formulari amb captcha (Turnstile), honeypot anti-spam, validació i consentiment RGPD.
- Sense cookies de seguiment; pàgines legals RGPD incloses.
- Cap dependència JavaScript de tercers excepte Turnstile.

## Visibilitat en IA (AI SEO)

- `llms.txt` amb el resum del negoci per a LLMs.
- `robots.txt` permet explícitament GPTBot, OAI-SearchBot, ClaudeBot,
  PerplexityBot, Google-Extended i altres.
- JSON-LD schema.org (`MedicalBusiness` + `Person`) a `index.html`.
