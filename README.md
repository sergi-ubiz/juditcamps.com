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

No cal cap build. Només un servidor estàtic:

```bash
python3 -m http.server 8080
# http://localhost:8080
```

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
