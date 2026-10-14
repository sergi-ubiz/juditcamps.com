# Memory Bank — juditcamps.com

Web professional de **Judit Camps Pujolar**, dietista-nutricionista a Taradell
(Osona). Aquest document és la **font única de veritat** del projecte: estat
actual, decisions i pendents, perquè qualsevol persona o IA (inclosos diversos
xats en paral·lel) hi continuï sense trepitjar-se.

- Data de creació: 12 d'octubre de 2026.
- Última actualització: 14 d'octubre de 2026 (analítica d'audiències pròpia;
  transferència de domini a GoDaddy, versió castellana, logo `es`, Turnstile).

---

## 0. ESTAT ACTUAL (llegeix-me primer)

- ✅ **WEB EN VIU AL DOMINI PROPI: https://juditcamps.com** (HTTP 200, TLS vàlid).
  - `www.juditcamps.com` → 301 a l'arrel; `http://` → 302 a `https://`.
  - Cloud Run (projecte `ultrabiz-admin`, regió `europe-west1`), servei
    `juditcamps`, revisió **`juditcamps-00009-t8z`** (13/10, commit `eec781b`).
  - URL interna: https://juditcamps-588935605619.europe-west1.run.app
  - `/api/health` respon 200 (`smtp_configured:false`, `turnstile_configured:true`).
- ✅ **Revisió legal RGPD / LOPDGDD / LSSI feta** (13/10): avís legal, privadesa i
  cookies (ca/es), NIF, núm. de col·legiada, consentiment de dades de salut.
- ✅ **Captcha (Turnstile) operatiu a producció**. Es carrega en interactuar
  amb el formulari i es reinicia després de cada enviament.
- **Identitat visual oficial aplicada** (logos reals de la Judit, paleta taupe +
  menta, tipografia Quicksand). Vegeu §3.
- ✅ **Domini connectat**: DNS a Dyn configurat (4 A + www CNAME), propietat
  verificada (`sergi@ultra-biz.net` és owner) i `domain-mappings` creats per
  arrel i `www`. Certificat TLS gestionat emès. Vegeu §7.
- 🟡 **Formulari: NO envia correus** fins que es configuri l'SMTP (§9).
  Mentrestant `/api/contact` respon 503 i el visitant veu un missatge que el
  convida a escriure a `info@juditcamps.com` (també visible a la secció de
  contacte).
- 🟡 **Analítica d'audiències pròpia FETA i commitejada, però NO desplegada**
  (sense cookies, tauler privat a `/stats/<STATS_TOKEN>/`). Provada en local
  (15 proves, nginx + gunicorn, navegador). Producció en viu encara és la
  revisió anterior, sense recollida. Vegeu §12b.

- 🟡 **Transferència de registrador a GoDaddy en curs** (juditcamps.com i
  ultra-biz.net, prevista 19/10). ⚠️ Abans de canviar nameservers cal corregir
  la zona pre-carregada de juditcamps.com a GoDaddy. Vegeu §7b.

### Blocadors (requereixen acció humana)
1. **App Password de Google per a `info@juditcamps.com`** (SMTP_USER +
   SMTP_PASSWORD) — §9. Necessari perquè el formulari enviï correus.
2. `gcloud auth login` (el token de `sergi@ultra-biz.net` havia caducat el
   13/10) per poder crear Firestore i desplegar l'analítica — §12b.

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
- Idioma: **català** (principal, públic d'Osona) + **castellà** a `/es/` (§12c).

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
- Execució local: **`python3 app.py`** → http://127.0.0.1:8080 (serveix
  l'estàtic + `/api/`, claus de prova de Turnstile i mode *dry-run*: el correu
  s'imprimeix a la consola en lloc d'enviar-se). ⚠️ `python3 -m http.server`
  no té backend: el captcha no es pinta i el formulari falla.

### Contenidor (Cloud Run)
Un sol contenidor (`Dockerfile`, base `python:3.12-slim`) amb **nginx +
gunicorn/Flask**:
- `nginx.conf`: serveix l'estàtic (gzip, cache 30d, capçaleres de seguretat),
  fa de **proxy de `/api/`** cap a `127.0.0.1:8000`, i **redirigeix
  `www.juditcamps.com` → `juditcamps.com`** (301).
  - ⚠️ CSS/JS es guarden 30 dies al navegador: **cada cop que es canviï
    `css/style.css` o `js/main.js`, cal pujar el `?v=AAAAMMDDNN`** dels enllaços a
    tots els HTML (ca i `es/`). Sense això, qui ja havia visitat la web rep el JS
    antic (el 13/10 va trencar el captcha).
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
  (pública, `0x4AAAAAAFVTt0n_d6bNRS3v`) l'injecta `entrypoint.sh` a
  `index.html` i `es/index.html`; el `secret` és a Secret Manager.
  - Render explícit i càrrega mandrosa (focus/clic al formulari, o en enviar
    sense token): cap visitant que no l'usi no contacta Cloudflare.
  - **Cada token és d'un sol ús**: `turnstile.reset()` després de cada resposta.
  - Missatges per estat HTTP: 400 captcha, 429 límit, 503 servei no disponible
    (SMTP), 404/405/501 sense backend.
- Consentiment: checkbox únic (privadesa + dades de salut art. 9.2.a RGPD +
  ≥14 anys o tutor). El correu inclou la versió de la política
  (`PRIVACY_POLICY_VERSION`) i el termini de conservació (12 mesos).

## 6. Seguretat

- **CSP** (meta a `index.html` i capçalera a `nginx.conf`, coherents):
  `default-src 'self'` + Turnstile (script/frame) + `font-src 'self'` (fonts
  Inter i Quicksand allotjades a `assets/fonts/`, sense Google Fonts) +
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

### Correu verificat després dels canvis DNS (13/10/2026)
- ✅ Els 7 MX de Google Workspace són intactes (comprovat contra el nameserver
  autoritatiu `ns1175.dns.dyn.com`): `ASPMX.L.GOOGLE.COM` (1), `ALT1/ALT2` (5),
  `ASPMX2-5.GOOGLEMAIL.COM` (10). El correu entrant funciona igual que abans.
- ⚠️ **Ja abans dels canvis, el domini no tenia SPF, DMARC ni DKIM.** No afecta la
  recepció, però sí l'entregabilitat del correu sortint (inclosos els avisos del
  formulari enviats com a `info@juditcamps.com`). Proposta pendent de confirmar:
  - SPF a `@`: `v=spf1 include:_spf.google.com ~all`
  - DMARC a `_dmarc`: `v=DMARC1; p=none; rua=mailto:info@juditcamps.com`
  - DKIM: activar-lo a admin.google.com (cal accés d'administrador del Workspace).
- ⚠️ **Si el domini es transfereix (p. ex. a GoDaddy) i el DNS deixa Dyn**: abans
  de canviar els nameservers, recrear a la nova zona **tots** els registres: els
  7 MX, els 2 TXT `google-site-verification`, els 4 A i el CNAME `www`. Si falten
  els MX, el correu de `info@juditcamps.com` deixa de rebre's; si falta el TXT
  `6137Zbe2…` o els A/CNAME, cau la web. Una transferència de registrador que
  manté els nameservers de Dyn no afecta res.

## 7b. Transferència de registrador a GoDaddy (EN CURS)

Objectiu: consolidar `juditcamps.com` i `ultra-biz.net` al compte GoDaddy
d'Ultrabiz (client 277226103), **sense cap tall de correu**. Restricció: no
tocar res del compte `ferranxx@gmail.com` (propietari del compte Dyn "skubix").
`restaurantauro.com` es deixa caducar a Sys4Net (decisió).

- 12/10/2026: tots dos dominis desbloquejats a Sys4Net (panell netlan), codis
  EPP introduïts a GoDaddy i transferència pagada (1 any cadascuna, factura
  ULTRABIZ SLU). Estat a `dcc.godaddy.com/control/transfers`: **"En curso"**,
  iniciada 12/10, prevista per al **19/10/2026** (pot arribar abans si
  Registrar.eu l'aprova).
- La transferència **no toca els nameservers**: el DNS continua a Dyn i tot
  (web + correu) funciona igual durant i després de la transferència.
- Zones pre-carregades a GoDaddy DNS hosting (nameservers assignats
  **`ns09.domaincontrol.com` / `ns10.domaincontrol.com`**), verificades amb
  `dig @ns09.domaincontrol.com`: MX i TXT idèntics a Dyn. Les zones DNS hosting
  sense producte associat s'esborren als 30 dies (la transferència acaba abans).
  - **ultra-biz.net** (16 registres): A `@` 80.31.93.204, CNAME `www` →
    ultra-biz.net, CNAME `admin` → ghs.googlehosted.com, 7 MX Google
    (prioritats 10–70), TXT `google-site-verification=nl3NFPF…`. Llesta.
  - ⚠️ **juditcamps.com: zona DESFASADA.** Es va carregar el 12/10 per a GitHub
    Pages (4 A `185.199.108–111.153`, CNAME `www` → `sergi-ubiz.github.io`).
    Ara la web és a Cloud Run: **abans de canviar nameservers** cal substituir-ho
    per les 4 A `216.239.32/34/36/38.21`, CNAME `www` → `ghs.googlehosted.com.`
    i afegir el TXT `google-site-verification=6137Zbe2…` (domain mapping). Els
    7 MX i el TXT `ewM1e5CS…` ja hi són.
- Editor de registres: `dcc.godaddy.com/control/portfolio/<domini>/settings?tab=dns`.
- Còpies de seguretat de les zones de Dyn: `assets-src/dyn-zones-backup-20261012.txt`
  i `assets-src/juditcamps.com-zone-backup-20261012.txt` (fora del repo).
- Quan acabi la transferència: corregir la zona de juditcamps.com, canviar els
  nameservers a ns09/ns10 i verificar amb `dig` web + MX abans de donar-ho per bo.

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

1. ✅ **Turnstile** (13/10): widget al compte Cloudflare d'Ultrabiz. Site key
   pública `0x4AAAAAAFVTt0n_d6bNRS3v` (env `TURNSTILE_SITE_KEY`, l'injecta
   `entrypoint.sh` a `index.html` i `es/index.html`). Secret a Secret Manager
   **`juditcamps-turnstile-secret`** (`ultrabiz-admin`) → env `TURNSTILE_SECRET`
   (accés `secretAccessor` per al compte de servei de Cloud Run).
   `CONTACT_TO=info@juditcamps.com` ja definit a Cloud Run.
2. ⏳ **SMTP Workspace**: `SMTP_USER` (p. ex. `info@juditcamps.com`) +
   `SMTP_PASSWORD` (**App Password**, requereix 2FA a la bústia). Opcional
   `SMTP_HOST`/`SMTP_PORT` (per defecte `smtp.gmail.com:587`).
3. **`CONTACT_TO`**: destinatari dels avisos (per defecte `info@juditcamps.com`).

Mentre no hi sigui l'SMTP, `/api/contact` respon 503 (el captcha sí que es pinta).

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
Balenyà 33, Taradell; formulari + alternativa per correu a `info@juditcamps.com`,
sense telèfon). Versió en castellà a `/es/` amb logo propi (`logo-es.png`).

CV (decisions del 13/10): professora de Dietoteràpia I i tutora de pràctiques
del grau de NHiD (UVic-UCC), +20 anys de consulta, especialitat digestiva.
**No es mencionen**: Centre Mèdic Vic, FORMANutricional, Duo Professionals ni
el perfil emprenedor/inversió.

## 12b. Analítica d'audiències pròpia (13/10/2026, vespre)

Decisió: **mesura pròpia, sense Google Analytics ni cap tercer, sense cookies**
(no cal bàner de consentiment). Codi a `analytics/` (domain, enrich, store,
report, routes + `dashboard/`), proves a `tests/test_analytics.py`.

- Recollida: `js/main.js` → `POST /api/pulse` (pageview, engagement en tancar la
  pestanya, conversió `contact_submit` quan el formulari s'envia bé).
- Visitant = HMAC(`ANALYTICS_SALT`, dia + IP + UA): rota cada dia, no es desa
  la IP. Sessió = pausa > 30 min. Rebot = criteri GA4 (< 10 s, 1 pàgina, sense
  conversió). Bots i Global Privacy Control exclosos.
- Geolocalització offline DB-IP City Lite (CC BY 4.0, cal atribució: és al
  tauler), descarregada al build (`scripts/download_geoip.py`, ~127 MB).
- Producció: Firestore, base de dades **`juditcamps`**, col·lecció
  `analytics_events`, TTL sobre `expire_at` (25 mesos, coherent amb la política
  de privadesa). Local: SQLite `analytics-local.sqlite3` (ignorat a git).
- Tauler privat: `/stats/<STATS_TOKEN>/` (nginx `location ^~ /stats/` sense
  access_log). Token incorrecte o no configurat → 404.
- Polítiques de privadesa i cookies (ca/es) actualitzades amb aquesta mesura.

- Notes de disseny: la sessió no pot travessar mitjanit (el hash és diari);
  "visitants" en rangs llargs = suma de visitants diaris; no es distingeix
  nou/recurrent (exigiria emmagatzematge al dispositiu). El tauler llegeix tots
  els esdeveniments del rang i agrega en Python (memòria cau 60 s): suficient
  pel volum actual; si creix molt, afegir agregats diaris precalculats.
- ⚠️ Amb `ANALYTICS_BACKEND` no definit, s'usa SQLite: a Cloud Run es perdria
  en cada arrencada. Cal `ANALYTICS_BACKEND=firestore` a producció.
- Els logs de petició de Cloud Run sí contenen l'URL amb el token (només
  visibles per als propietaris del projecte GCP).
- Enllaços de campanya: `?utm_source=instagram&utm_medium=social`,
  `utm_medium=qr` per a fulletons/targetes.

### Desplegament pendent (cal `gcloud auth login`, el token havia caducat)
```bash
gcloud services enable firestore.googleapis.com --project ultrabiz-admin
gcloud firestore databases create --database=juditcamps \
  --location=europe-west1 --type=firestore-native --project ultrabiz-admin
gcloud firestore fields ttls update expire_at --collection-group=analytics_events \
  --enable-ttl --database=juditcamps --project ultrabiz-admin
# El compte de servei de Cloud Run necessita roles/datastore.user.
gcloud run deploy juditcamps --source . --region europe-west1 ... \
  --update-env-vars ANALYTICS_BACKEND=firestore,ANALYTICS_FIRESTORE_DB=juditcamps,\
STATS_TOKEN=<secret>,ANALYTICS_SALT=<secret>
```

## 13. Pendent / pròxims passos

0. **Dades legals** (revisió legal del 13/10): ✅ NIF 47792007P i col·legiada
   CoDiNuCat núm. CAT000088 ja posats (format oficial CAT + 6 xifres; la
   signatura del seu correu diu CAT00088). Adreça Ctra. de Balenyà 33 confirmada.
   Ja no treballa al Centre Mèdic Vic ni a FORMANutricional: no es mencionen, ni
   Duo Professionals ni el perfil emprenedor/inversió (decisió 13/10).
   Pendent: si cal publicar el número de registre sanitari del centre.
   CV ampliat: professora de Dietoteràpia I al grau de NHiD de la UVic (des del
   curs 2025-26, font: correu de proposta docent i uvic.cat/assignatura/4761),
   tutora de pràctiques, curs de nutrició esportiva (UB).
   Canvis fets: fonts allotjades localment (sense Google Fonts), Turnstile es
   carrega només en interactuar amb el formulari, informació de primera capa
   RGPD al formulari, consentiment explícit (art. 9.2.a) per a dades de salut,
   constància del consentiment al correu, i correu `info@juditcamps.com` publicat
   a les pàgines legals (exigit per l'art. 10 LSSI).
1. **App Password SMTP** (§9) → desar a Secret Manager + redeploy. **Únic
   pendent crític** perquè el formulari de contacte enviï correus.
2. ✅ ~~DNS a Dyn + domain mapping~~ — FET (§7). `https://juditcamps.com` en viu.
3. Opcional: esborrar `_headers` (codi mort a Cloud Run).
4. Opcional: og-image amb foto professional de la Judit.
5. Opcional: recuperar la botiga de l'ebook "12 mesos, 12 canvis" i la reserva
   de cita online (no migrades de la web antiga).
6. Opcional: moure DNS a Cloud DNS si es vol IPv6 (AAAA) complet.
7. **Desplegar l'analítica** (§12b): Firestore `juditcamps` + TTL, generar
   `STATS_TOKEN` i `ANALYTICS_SALT` (millor a Secret Manager), deploy amb
   `ANALYTICS_BACKEND=firestore`, verificar `/api/pulse` i passar l'enllaç
   privat del tauler a la Judit.
8. Opcional: refrescar la base GeoIP (DB-IP publica cada mes; es renova sola a
   cada redeploy).
9. Afegir SPF + DMARC i activar DKIM al Workspace (§7, pendent de confirmar).
   Recomanat abans d'activar el formulari.
10. **Transferència GoDaddy** (§7b): vigilar fins al ~19/10; quan acabi,
    corregir la zona de juditcamps.com a GoDaddy (Cloud Run, no GitHub Pages)
    i després canviar nameservers de tots dos dominis a ns09/ns10.
11. La Judit no recorda la contrasenya d'`info@juditcamps.com`: cal que
    l'administrador del Workspace la restableixi per poder generar l'App
    Password (desbloqueja el punt 1).
