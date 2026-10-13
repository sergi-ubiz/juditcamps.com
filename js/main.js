/**
 * juditcamps.com — interaccions de la pàgina.
 * - Menú mòbil accessible
 * - Animacions "reveal" amb IntersectionObserver
 * - Enviament del formulari de contacte al backend propi (/api/contact)
 * - Turnstile es carrega només quan l'usuari interactua amb el formulari, perquè
 *   cap visitant que no l'utilitzi enviï dades a Cloudflare.
 */
(function () {
    "use strict";

    /* Any actual al peu */
    var yearEl = document.getElementById("year");
    if (yearEl) {
        yearEl.textContent = String(new Date().getFullYear());
    }

    /* Menú mòbil */
    var toggle = document.querySelector(".nav-toggle");
    var links = document.querySelector(".nav-links");
    if (toggle && links) {
        toggle.addEventListener("click", function () {
            var open = links.classList.toggle("open");
            toggle.setAttribute("aria-expanded", String(open));
        });
        links.addEventListener("click", function (e) {
            if (e.target.tagName === "A") {
                links.classList.remove("open");
                toggle.setAttribute("aria-expanded", "false");
            }
        });
    }

    /* Animacions reveal */
    try {
        var observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.12 }
        );
        document.querySelectorAll(".reveal").forEach(function (el) {
            observer.observe(el);
        });
    } catch (err) {
        /* Navegadors antics: mostrar-ho tot */
        document.querySelectorAll(".reveal").forEach(function (el) {
            el.classList.add("visible");
        });
    }

    /* Formulari de contacte */
    var form = document.querySelector(".contact-form");
    if (!form) return;
    var statusEl = form.querySelector(".form-status");

    var messages = {
        ca: {
            captchaLoad: "No s'ha pogut carregar la verificació de seguretat.",
            captchaMissing: "Si us plau, completa la verificació de seguretat.",
            sending: "Enviant…",
            sent: "Missatge enviat. Et respondré tan aviat com pugui!",
            failed: "No s'ha pogut enviar. Torna-ho a provar d'aquí a uns minuts.",
            network: "Error de connexió. Torna-ho a provar més tard.",
            captchaFailed: "La verificació de seguretat ha caducat. Torna-la a fer i " +
                "envia de nou.",
            unavailable: "Ara mateix el formulari no està disponible. Escriu-me a " +
                "info@juditcamps.com.",
            tooMany: "Has enviat massa sol·licituds. Torna-ho a provar més tard.",
            noBackend: "Aquest servidor local no té backend: arrenca'l amb " +
                "«python3 app.py»."
        },
        es: {
            captchaLoad: "No se ha podido cargar la verificación de seguridad.",
            captchaMissing: "Por favor, completa la verificación de seguridad.",
            sending: "Enviando…",
            sent: "Mensaje enviado. ¡Te responderé lo antes posible!",
            failed: "No se ha podido enviar. Vuelve a intentarlo en unos minutos.",
            network: "Error de conexión. Vuelve a intentarlo más tarde.",
            captchaFailed: "La verificación de seguridad ha caducado. Vuelve a " +
                "hacerla y envía de nuevo.",
            unavailable: "Ahora mismo el formulario no está disponible. Escríbeme a " +
                "info@juditcamps.com.",
            tooMany: "Has enviado demasiadas solicitudes. Vuelve a intentarlo más " +
                "tarde.",
            noBackend: "Este servidor local no tiene backend: arráncalo con " +
                "«python3 app.py»."
        }
    };
    var text = messages[document.documentElement.lang] || messages.ca;

    var turnstileRequested = false;
    function loadTurnstile() {
        if (turnstileRequested) return;
        turnstileRequested = true;
        window.onTurnstileLoad = function () {
            try {
                var widget = form.querySelector(".cf-turnstile");
                var isLocalHost = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
                if (isLocalHost && widget.dataset.sitekey === "TURNSTILE_SITE_KEY") {
                    /* Clau de prova oficial de Cloudflare: sempre valida */
                    widget.dataset.sitekey = "1x00000000000000000000AA";
                }
                window.turnstile.render(widget);
            } catch (err) {
                setStatus(text.captchaLoad, true);
            }
        };
        var script = document.createElement("script");
        script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js" +
            "?render=explicit&onload=onTurnstileLoad";
        script.async = true;
        script.onerror = function () {
            setStatus(text.captchaLoad, true);
        };
        document.head.appendChild(script);
    }
    form.addEventListener("focusin", loadTurnstile);
    form.addEventListener("pointerdown", loadTurnstile);

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        /* Honeypot: si està ple, és un bot */
        var hp = form.querySelector('input[name="_gotcha"]');
        if (hp && hp.value) return;

        /* Validació nativa */
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        /* Captcha Turnstile obligatori */
        var tokenInput = form.querySelector('input[name="cf-turnstile-response"]');
        if (!tokenInput || !tokenInput.value) {
            loadTurnstile();
            setStatus(text.captchaMissing, true);
            return;
        }

        setStatus(text.sending, false);
        var btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;

        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { Accept: "application/json" }
        })
            .then(function (res) {
                if (res.ok) {
                    form.reset();
                    setStatus(text.sent, false);
                } else {
                    setStatus(errorMessageFor(res.status), true);
                }
            })
            .catch(function () {
                setStatus(text.network, true);
            })
            .finally(function () {
                btn.disabled = false;
                /* Cada token de Turnstile només es pot validar una vegada */
                if (window.turnstile) window.turnstile.reset();
            });
    });

    function errorMessageFor(status) {
        if (status === 400) return text.captchaFailed;
        if (status === 429) return text.tooMany;
        if (status === 503) return text.unavailable;
        if (status === 404 || status === 405 || status === 501) return text.noBackend;
        return text.failed;
    }

    function setStatus(msg, isError) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.className = "form-status " + (isError ? "error" : "ok");
    }
})();
