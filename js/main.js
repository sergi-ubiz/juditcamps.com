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

    var turnstileRequested = false;
    function loadTurnstile() {
        if (turnstileRequested) return;
        turnstileRequested = true;
        window.onTurnstileLoad = function () {
            try {
                window.turnstile.render(".cf-turnstile");
            } catch (err) {
                setStatus("No s'ha pogut carregar la verificació de seguretat.", true);
            }
        };
        var script = document.createElement("script");
        script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js" +
            "?render=explicit&onload=onTurnstileLoad";
        script.async = true;
        script.onerror = function () {
            setStatus("No s'ha pogut carregar la verificació de seguretat.", true);
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
            setStatus("Si us plau, completa la verificació de seguretat.", true);
            return;
        }

        setStatus("Enviant…", false);
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
                    if (window.turnstile) window.turnstile.reset();
                    setStatus("Missatge enviat. Et respondré tan aviat com pugui!", false);
                } else {
                    setStatus("No s'ha pogut enviar. Torna-ho a provar d'aquí a uns minuts.", true);
                }
            })
            .catch(function () {
                setStatus("Error de connexió. Torna-ho a provar més tard.", true);
            })
            .finally(function () {
                btn.disabled = false;
            });
    });

    function setStatus(msg, isError) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.className = "form-status " + (isError ? "error" : "ok");
    }
})();
