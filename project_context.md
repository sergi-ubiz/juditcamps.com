# Memory Bank — juditcamps.com

Web professional de **Judit Camps Pujolar**, dietista-nutricionista a Taradell
(Osona). Aquest document és la **font única de veritat** del projecte: estat
actual, decisions i pendents, perquè qualsevol persona o IA (inclosos diversos
xats en paral·lel) hi continuï sense trepitjar-se.

- Data de creació: 12 d'octubre de 2026.
- Última actualització: 13 d'octubre de 2026 (matinada).

---

## 0. ESTAT ACTUAL (llegeix-me primer)

- ✅ **WEB EN VIU AL DOMINI PROPI: https://juditcamps.com** (HTTP 200, TLS vàlid).
  - `www.juditcamps.com` → 301 a l'arrel; `http://` → 302 a `https://`.
  - Cloud Run (projecte `ultrabiz-admin`, regió `europe-west1`), servei
    `juditcamps`, revisió `juditcamps-00004`.
  - URL interna: https://juditcamps-588935605619.europe-west1.run.app
  - `/api/health` respon 200 (`smtp_configured:false`, `turnstile_configured:false`).
- **Identitat visual oficial aplicada** (logos reals de la Judit, paleta taupe +
  menta, tipografia Quicksand). Vegeu §3.
- ✅ **Domini connectat**: DNS a Dyn configurat (4 A + www CNAME), propietat
  verificada (`sergi@ultra-biz.net` és owner) i `domain-mappings` creats per
  arrel i `www`. Certificat TLS gestionat emès. Vegeu §7.
- **Formulari propi muntat** (backend Flask a Cloud Run), però **NO operatiu**
  fins que s'injectin 3 secrets (Turnstile + SMTP). Vegeu §6 i §9.

### Blocadors (requereixen acció humana)
1. Proporcionar secrets del formulari (Turnstile SITE+SECRET, SMTP_USER+
   SMTP_PASSWORD, CONTACT_TO) — §9. **És l'únic pendent perquè tot funcioni.**

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

### Registres DNS a Dyn (✅ FETS el 13/10/2026)
| Tipus | Nom | Valor | Estat |
|-------|-----|-------|-------|
| TXT | `@` | `google-site-verification=6137Zbe2AzG19FrPPuhCnvr0Ksvhda_2mAqnK-gJR2w` | ✅ afegit i propagat |
| A | `@` | `216.239.32.21`, `216.239.34.21`, `216.239.36.21`, `216.239.38.21` | ✅ afegits i propagats |
| CNAME | `www` | `ghs.googlehosted.com.` | ✅ canviat (abans `parked.everydns.net`) |

- ⚠️ **AAAA (IPv6) NO afegits**: el producte "Dyn Standard DNS" només admet
  IPv4 al formulari d'hostnames (rebutja IPv6). La web és accessible per IPv4
  (99% dels clients). Si es vol IPv6 complet, cal moure el DNS a Cloud DNS.
- Mantinguts el TXT `google-site-verification=ewM1e5CS-…` existent i tots els MX.
- Accés fet via portal web `account.dyn.com` (usuari `skubix`). ⚠️ La contrasenya
  es va compartir al xat; recomanat canviar-la.

### Passos ja completats (13/10/2026)
1. ✅ Propietat verificada via API siteVerification (owner `sergi@ultra-biz.net`).
2. ✅ `gcloud beta run domain-mappings create` per `juditcamps.com` i
   `www.juditcamps.com` (regió `europe-west1`, projecte `ultrabiz-admin`).
3. ✅ Cloud Run ha emès el certificat TLS gestionat; `https://juditcamps.com`
   serveix correctament.

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

0. **Dades legals** (revisió legal del 13/10): ✅ NIF 47792007P i col·legiada
   CoDiNuCat núm. CAT000088 ja posats. Pendent de confirmar amb la Judit:
   número del Peu Peu (la web diu Ctra. de Balenyà 33, el seu LinkedIn diu 28),
   si encara passa consulta al Centre Mèdic Vic (afegit al CV des del LinkedIn)
   i si cal publicar el número de registre sanitari del centre.
   CV ampliat: professora de Dietoteràpia I al grau de NHiD de la UVic (des del
   curs 2025-26, font: correu de proposta docent i uvic.cat/assignatura/4761),
   tutora de pràctiques, FORMANutricional, curs de nutrició esportiva (UB).
   Canvis fets: fonts allotjades localment (sense Google Fonts), Turnstile es
   carrega només en interactuar amb el formulari, informació de primera capa
   RGPD al formulari, consentiment explícit (art. 9.2.a) per a dades de salut,
   constància del consentiment al correu, i correu `info@juditcamps.com` publicat
   a les pàgines legals (exigit per l'art. 10 LSSI).
1. **Secrets del formulari** (§9) → desar a Secret Manager + redeploy. **Únic
   pendent crític** perquè el formulari de contacte funcioni.
2. ✅ ~~DNS a Dyn + domain mapping~~ — FET (§7). `https://juditcamps.com` en viu.
3. Opcional: esborrar `_headers` (codi mort a Cloud Run).
4. Opcional: og-image amb foto professional de la Judit.
5. Opcional: recuperar la botiga de l'ebook "12 mesos, 12 canvis" i la reserva
   de cita online (no migrades de la web antiga).
6. Opcional: moure DNS a Cloud DNS si es vol IPv6 (AAAA) complet.
