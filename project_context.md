# Memory Bank — juditcamps.com

Web professional de **Judit Camps Pujolar**, dietista-nutricionista a Taradell
(Osona). Aquest document és la **font única de veritat** del projecte: estat
actual, decisions i pendents, perquè qualsevol persona o IA (inclosos diversos
xats en paral·lel) hi continuï sense trepitjar-se.

- Data de creació: 12 d'octubre de 2026.
- Última actualització: 12 d'octubre de 2026 (nit).

---

## 0. ESTAT ACTUAL (llegeix-me primer)

- **Web en viu a Cloud Run** (projecte `ultrabiz-admin`, regió `europe-west1`):
  - Servei `juditcamps`, revisió en producció `juditcamps-00003`.
  - URL provisional: https://juditcamps-588935605619.europe-west1.run.app
  - Contingut estàtic OK; `/api/health` respon 200.
- **Identitat visual oficial aplicada** (logos reals de la Judit, paleta taupe +
  menta, tipografia Quicksand). Vegeu §3.
- **Formulari propi muntat** (backend Flask a Cloud Run), però **NO operatiu**
  fins que s'injectin 3 secrets (Turnstile + SMTP). Vegeu §6 i §9.
- **Domini `juditcamps.com` encara NO connectat**: pendent que s'afegeixin els
  registres DNS a Dyn i després verificar + mapar. Vegeu §7.
- ⚠️ **DOS XATS han treballat en paral·lel** sobre el mateix repo i servei
  (han muntat el mateix backend i un ha tret telèfon/correu de la web). Cal que
  **un sol xat remati** per no duplicar desplegaments. Vegeu §10.

### Blocadors (requereixen acció humana)
1. Afegir registres DNS a Dyn (TXT + A/AAAA + www CNAME) — §7.
2. Proporcionar secrets del formulari (Turnstile SITE+SECRET, SMTP_USER+
   SMTP_PASSWORD, CONTACT_TO) — §9.

---

## 1. Objectiu

Web moderna, d'estil fi i elegant, que transmeti qualitat, força i convicció.
Exposa l'experiència de la Judit, què fa i què ofereix, i permet contactar-la
de forma segura (formulari amb captcha). Ha de ser visible tant a cercadors
clàssics com a assistents d'IA (ChatGPT, Claude, Perplexity…).

## 2. Origen del contingut

- La web antiga `juditcamps.com` (Weebly) va desaparèixer; està **arxivada a la
  Wayback Machine** (snapshots de 2021). Tot el contingut real s'ha recuperat
  d'allà. **No hi ha contingut inventat.** Còpies dels HTML originals a
  `assets-src/` (no es puja al repo).
- Idioma: **català** (públic d'Osona).

## 3. Identitat visual (ACTUALITZADA 12/10/2026)

La Judit va enviar els logos oficials (rebuts com a imatges, originals JPG
desats a `assets-src/jc-logo-wordmark.jpg` i `assets-src/jc-logo-badge.jpg`).
S'han adaptat a la web:

- **Logo de capçalera**: `assets/logo.png` — wordmark "JUDIT CAMPS /
  Dietètica i Nutrició" (PNG amb fons transparent). Al header de totes les
  pàgines.
- **Segell**: `assets/logo-badge.png` — cercle amb fulla "DIETÈTICA I NUTRICIÓ
  · JUDIT CAMPS". Al footer (en blanc sobre fons taupe).
- **Favicon**: `assets/favicon.svg` — fulla menta dins cercle, redibuixat fidel
  al segell.
- **og-image**: `assets/og-image.jpg` (1200×630) regenerada amb la marca nova
  (plantilla font `assets-src/og-card.html`).
- **Paleta** (a `css/style.css`, `:root`):
  - Taupe fosc titulars `--green-900: #5a4f4c`
  - Taupe de marca `--green-700: #857774` (text secundari, enllaços)
  - Menta fosc accents `--green-500: #4aa98c`
  - Menta de marca `--green-300: #7cccaf` (decoració)
  - Crema `--cream: #fbfaf8`, sorra `--sand: #f3efec`
  - (Els noms de variable mantenen el prefix `--green-*` per compatibilitat.)
- **Tipografia**: **Quicksand** (geomètrica arrodonida, titulars) + **Inter**
  (cos), via Google Fonts. (Abans era Cormorant Garamond.)

## 4. Arquitectura tècnica (ACTUALITZADA)

### Stack
- Web **estàtica** (HTML + CSS + JS vanilla, sense build ni npm) + un **backend
  mínim** només per al formulari.
- Execució local de l'estàtic: `python3 -m http.server 8080`.

### Contenidor (Cloud Run)
Un sol contenidor (`Dockerfile`, base `python:3.12-slim`) amb **nginx +
gunicorn/Flask**:
- `nginx.conf`: serveix l'estàtic (gzip, cache 30d, capçaleres de seguretat),
  fa de **proxy de `/api/`** cap a `127.0.0.1:8000`, i **redirigeix
  `www.juditcamps.com` → `juditcamps.com`** (301).
- `entrypoint.sh`: injecta `TURNSTILE_SITE_KEY` a l'HTML (si està a l'entorn),
  arrenca gunicorn, **espera que escolti** i només llavors obre nginx (evita els
  **502 d'arrencada en fred**).
- `app.py` (Flask) + `requirements.txt` (Flask, gunicorn, requests).

### Desplegament
- Ordre: `gcloud run deploy juditcamps --source . --region europe-west1
  --allow-unauthenticated --port 8080 --cpu 1 --memory 512Mi
  --min-instances 0 --max-instances 3 --project ultrabiz-admin --quiet`
- Build via Cloud Build; imatges a Artifact Registry
  (`cloud-run-source-deploy`, europe-west1).
- GCP: compte `sergi@ultra-biz.net`, projecte `ultrabiz-admin`, billing actiu.
  APIs activades: run, cloudbuild, artifactregistry, siteverification.

## 5. Formulari de contacte (ACTUALITZAT: backend propi, sense Formspree)

Decisió (12/10): **el servei és nostre**, no extern. Formspree eliminat.

- Frontend: `<form action="/api/contact">` + `js/main.js` (fetch, estats
  accessibles `aria-live`, honeypot `_gotcha`, validació HTML5, checkbox RGPD).
- Backend `app.py`, endpoint **`POST /api/contact`**:
  1. Valida camps (nom, email, telèfon, missatge) i consentiment.
  2. **Verifica el token de Turnstile al servidor** (Cloudflare siteverify).
  3. **Envia el correu** a `CONTACT_TO` via **SMTP del Google Workspace** de la
     Judit (STARTTLS, `smtp.gmail.com:587`), amb `Reply-To` del remitent.
  - Defenses: honeypot, rate-limit en memòria (5/h per IP), validació estricta.
- `GET /api/health`: retorna estat i si Turnstile/SMTP estan configurats.
- Captcha: **Cloudflare Turnstile** (privadesa, sense puzzles). La `site key`
  (pública) s'injecta a l'HTML al desplegament; el `secret` viu al backend.

## 6. Seguretat

- **CSP** (meta a `index.html` i capçalera a `nginx.conf`, coherents):
  `default-src 'self'` + Turnstile (script/frame) + Google Fonts +
  `connect-src 'self'` + `form-action 'self'` + `object-src 'none'` +
  `base-uri 'self'`.
- Capçaleres: HSTS, `X-Frame-Options: DENY`, `X-Content-Type-Options`,
  `Referrer-Policy`, `Permissions-Policy`.
- `credentials/` i `assets-src/` exclosos del repo (`.gitignore`); `__pycache__`
  exclòs del build (`.dockerignore`).
- Nota: el fitxer `_headers` (format Netlify/Cloudflare) ja **no s'usa** a Cloud
  Run (replicat a `nginx.conf`); és codi mort, es pot esborrar.

## 7. Domini i DNS (juditcamps.com)

- **Propietat de la Judit**, registrat des del 2010, pagat fins al 30/09/2027
  (Registrar.eu / Hosting Concepts).
- **DNS a Dyn** (compte "skubix", ferranxx@gmail.com), nameservers
  `ns1175 / ns2138 / ns3147 / ns4173.dns.dyn.com`.
- **MX de Google Workspace actius** (`info@juditcamps.com` funciona). ⚠️ **NO
  tocar els MX.**
- **Canònic = arrel `juditcamps.com`** (sense www). Unificat a HTML, `sitemap.xml`,
  `robots.txt`, `llms.txt`. `www` redirigeix a l'arrel (a nginx).

### Registres a afegir a Dyn (pendents de propagar-se)
| Tipus | Nom | Valor |
|-------|-----|-------|
| TXT | `@` | `google-site-verification=6137Zbe2AzG19FrPPuhCnvr0Ksvhda_2mAqnK-gJR2w` |
| A | `@` | `216.239.32.21`, `216.239.34.21`, `216.239.36.21`, `216.239.38.21` |
| AAAA | `@` | `2001:4860:4802:32::15`, `…:34::15`, `…:36::15`, `…:38::15` |
| CNAME | `www` | `ghs.googlehosted.com.` (substitueix `parked.everydns.net`) |

Mantenir el TXT `google-site-verification=ewM1e5CS-…` existent i tots els MX.

### Passos un cop el DNS estigui propagat
1. Verificar propietat (API siteVerification, ja amb scope a l'ADC) o
   `gcloud domains verify juditcamps.com`.
2. `gcloud beta run domain-mappings create --service juditcamps
   --domain juditcamps.com --region europe-west1 --project ultrabiz-admin`.
3. Cloud Run emet el certificat TLS gestionat automàticament.

## 8. SEO + visibilitat en IA (AI SEO / GEO)

- **JSON-LD schema.org** a `index.html`: `MedicalBusiness` + `Person` niuat.
- **`llms.txt`**: resum per a LLMs. **`robots.txt`**: permet GPTBot,
  OAI-SearchBot, ClaudeBot, Google-Extended, PerplexityBot, etc.
- `sitemap.xml`, meta description, Open Graph, canonical a `https://juditcamps.com/`.
- Pàgines legals (`avis-legal.html`, `privadesa.html`, `cookies.html`) amb
  `noindex, follow`.

## 9. Secrets pendents del formulari (acció humana)

Cal proporcionar-los; després es desen a **Secret Manager** / variables d'entorn
de Cloud Run i es redesplega. `app.py` els llegeix de l'entorn:

1. **Turnstile** (Cloudflare, gratis): `TURNSTILE_SITE_KEY` (pública, s'injecta
   a l'HTML) + `TURNSTILE_SECRET` (backend).
2. **SMTP Workspace**: `SMTP_USER` (p. ex. `info@juditcamps.com`) +
   `SMTP_PASSWORD` (**App Password**, requereix 2FA a la bústia). Opcional
   `SMTP_HOST`/`SMTP_PORT` (per defecte `smtp.gmail.com:587`).
3. **`CONTACT_TO`**: destinatari dels avisos (per defecte `info@juditcamps.com`).

Mentre no hi siguin, `/api/contact` respon 503 i el captcha no es pinta.

## 10. Coordinació entre xats (IMPORTANT)

El 12/10 dos xats van treballar alhora sobre aquest mateix directori i servei:
- Un va fer la identitat visual, el desplegament a Cloud Run, el canònic a
  l'arrel i la correcció del 502 en fred.
- L'altre va muntar també el backend del formulari i va **treure telèfon/correu**
  de la web (contacte només via formulari).

Tot està consolidat a la revisió `juditcamps-00003`. **Regla: un sol xat ha de
rematar** (secrets + DNS + domain mapping) per evitar desplegaments i commits
que es trepitgin. Abans de tocar res, feu `git pull` i reviseu aquest document.

## 11. Repositori

- GitHub: `sergi-ubiz/juditcamps.com`, branca `main`.
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).
- També es va activar **GitHub Pages** en una fase anterior (hosting estàtic);
  el hosting principal ara és **Cloud Run**.

## 12. Contingut de la pàgina (resum)

Seccions one-page: Hero ("L'alimentació és font de vida i salut") · Filosofia ·
Qui sóc (bio real + 4 titulacions, +20 anys) · Serveis (salut digestiva [la seva
especialitat], intoleràncies/al·lèrgies, etapes de la vida, salut metabòlica,
objectius personals) · Mètode (4 passos) · Contacte (centre Peu Peu, Ctra. de
Balenyà 33, Taradell — **ara només via formulari**, sense telèfon/correu a la
vista). Adreça encara visible.

## 13. Pendent / pròxims passos

1. **Secrets del formulari** (§9) → desar a Secret Manager + redeploy.
2. **DNS a Dyn** (§7) → verificar propietat + `domain-mappings create`.
3. Opcional: esborrar `_headers` (codi mort a Cloud Run).
4. Opcional: og-image amb foto professional de la Judit.
5. Opcional: recuperar la botiga de l'ebook "12 mesos, 12 canvis" i la reserva
   de cita online (no migrades de la web antiga).
