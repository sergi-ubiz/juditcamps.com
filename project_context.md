# Project Context — juditcamps.com

Web professional de **Judit Camps Pujolar**, dietista-nutricionista a Taradell
(Osona). Aquest document recull totes les decisions tècniques i funcionals del
projecte per a qualsevol persona (o IA) que hi continuï treballant.

Data de creació: 12 d'octubre de 2026.

---

## 1. Objectiu

Crear una web moderna, d'estil fi i elegant — com ella — que transmeti alhora
qualitat, força i convicció. Ha d'exposar la seva llarga experiència
professional, explicar què fa i què ofereix, i permetre contactar-la de forma
segura (formulari amb captcha). Ha de ser visible tant a cercadors clàssics
com a assistents d'IA (ChatGPT, Claude, Perplexity…).

## 2. Origen del contingut

- La web antiga `juditcamps.com` (feta amb Weebly) va desaparèixer, però està
  **arxivada a la Wayback Machine** (snapshots de 2021).
- Tot el contingut real s'ha recuperat d'allà: filosofia, biografia, formació,
  llista completa de serveis i dades de contacte. **No hi ha contingut
  inventat.** Còpies dels HTML originals a `assets-src/` (no es puja al repo).
- El **logo original no estava arxivat** (ni es va trobar a Gmail/Drive).
  S'ha creat un wordmark SVG nou (`assets/logo.svg`): monograma "jc" dins un
  cercle fi amb motiu de fulles + "Judit Camps / DIETISTA · NUTRICIONISTA".
  És un punt de partida substituïble si apareix el logo original.

## 3. Decisions tècniques

### Stack: web estàtica sense build
- **HTML + CSS + JavaScript vanilla.** Cap framework, cap bundler, cap
  dependència de npm.
- Motius: contingut essencialment estàtic, màxima velocitat, superfície
  d'atac mínima, manteniment trivial a llarg termini, desplegable gratis a
  qualsevol hosting estàtic.
- Execució local: `python3 -m http.server 8080`.

### Disseny
- Paleta: verds salvia (`#2f3e2f`, `#5a7d5a`, `#b7c9a8`) + neutres càlids
  (`#faf8f3`, `#f1ece1`). Transmet salut, natura i serenor.
- Tipografia: **Cormorant Garamond** (serif fina, títols) + **Inter** (cos),
  via Google Fonts.
- One-page amb seccions ancorades (filosofia, qui sóc, serveis, mètode,
  contacte) + pàgines legals separades.
- Animacions "reveal" amb IntersectionObserver, amb respecte per
  `prefers-reduced-motion` i fallback per a navegadors antics.
- Responsive amb menú hamburguesa accessible (aria-expanded).

### Formulari de contacte
- **Formspree** com a backend (no hi ha servidor propi): `action` a
  `https://formspree.io/f/FORMSPREE_ID` — **pendent de substituir l'ID real**.
- **Captcha: Cloudflare Turnstile** (no reCAPTCHA, per privadesa i UX sense
  puzzles). Placeholder `TURNSTILE_SITE_KEY` a `index.html` — **pendent de
  crear el widget** pel domini i activar la verificació del token a Formspree.
- Defensa en profunditat: honeypot (`_gotcha`), validació nativa HTML5 +
  `checkValidity()`, checkbox de consentiment RGPD obligatori, enviament via
  `fetch` amb gestió d'errors i missatges d'estat accessibles (`aria-live`).

### Seguretat
- **CSP estricta** (meta a `index.html` i capçalera a `_headers`): només
  `self` + Turnstile + Google Fonts + Formspree com a `form-action`.
  `object-src 'none'`, `base-uri 'self'`.
- `_headers` (format Netlify/Cloudflare Pages): HSTS, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- **Zero cookies pròpies de seguiment** — simplifica el compliment RGPD;
  només Turnstile pot posar cookies tècniques (documentat a `cookies.html`).
- `credentials/` i `assets-src/` exclosos del repo via `.gitignore`.

### SEO + visibilitat en assistents d'IA (AI SEO / GEO)
- **JSON-LD schema.org** a `index.html`: `MedicalBusiness` (adreça, telèfon,
  especialitat, àrea de servei) + `Person` niuat (formació, `knowsAbout`).
- **`llms.txt`**: resum estructurat del negoci pensat per a LLMs.
- **`robots.txt`**: permet explícitament GPTBot, OAI-SearchBot, ChatGPT-User,
  ClaudeBot, anthropic-ai, Google-Extended, PerplexityBot, Applebot-Extended,
  cohere-ai.
- `sitemap.xml`, meta description, Open Graph, canonical a
  `https://www.juditcamps.com/`.
- Pàgines legals amb `noindex, follow`.

### Repositori
- GitHub: `sergi-ubiz/juditcamps.com` (privat), branca `main`.
- Convenció de commits: conventional commits (`feat:`, `fix:`, `docs:`…).

## 4. Decisions funcionals (contingut)

- **Idioma: català** (com la web original; el seu públic és d'Osona).
- Seccions de la pàgina principal:
  1. **Hero** — claim "L'alimentació és font de vida i salut" (de la seva
     filosofia) + CTA "Demana una primera visita".
  2. **Filosofia** — text original d'ella, lleugerament editat.
  3. **Qui sóc** — biografia real (filla de restauradors, especialització en
     patologies digestives viscudes en primera persona, visió integral) +
     targeta de credencials (4 titulacions, +20 anys d'experiència).
  4. **Serveis** — la llista original de "Et puc ajudar en" reorganitzada en
     5 grups: salut digestiva (etiquetada com la seva especialitat),
     intoleràncies i al·lèrgies, etapes de la vida, salut metabòlica i
     objectius personals.
  5. **Mètode** — els 4 passos descrits a la web antiga: estudiar el cas,
     modificar hàbits, personalitzar la dieta, acompanyar el procés.
  6. **Contacte** — centre Peu Peu, Ctra. de Balenyà 33, Taradell ·
     660 347 743 · info@juditcamps.com + formulari.
- Pàgines legals RGPD: `avis-legal.html`, `privadesa.html`, `cookies.html`.
- De la web antiga **no s'ha migrat** (de moment): la botiga/ebook
  "12 mesos, 12 canvis" i la pàgina de reserva de cita online.

## 5. Estat del domini (12/10/2026)

- `juditcamps.com` és **propietat d'ella**, registrat des del 2010 i pagat
  fins al **30/09/2027** (Registrar.eu / Hosting Concepts).
- DNS delegat a **Dyn** (`ns*.dns.dyn.com`).
- **No té registres A/CNAME** → la web no resol (per això va desaparèixer).
- **MX de Google actius** → `info@juditcamps.com` funciona. ⚠️ Si es canvien
  els nameservers, cal replicar els MX perquè el correu no caigui.

## 6. Pendent / pròxims passos

1. Crear formulari a Formspree i substituir `FORMSPREE_ID` a `index.html`.
2. Crear widget Cloudflare Turnstile pel domini i substituir
   `TURNSTILE_SITE_KEY`; activar verificació del token a Formspree.
3. Afegir `assets/og-image.jpg` (1200×630) amb foto professional de la Judit.
4. Triar hosting estàtic (recomanat: Cloudflare Pages o GitHub Pages) i
   apuntar-hi el DNS (A/CNAME a Dyn, o migrar DNS a Cloudflare conservant
   els MX de Google).
5. Opcional: recuperar la botiga de l'ebook i la reserva de cita online.
6. Opcional: substituir el wordmark si apareix el logo original.
