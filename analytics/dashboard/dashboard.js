/**
 * Tauler d'audiència privat de juditcamps.com.
 *
 * L'estat (període, granularitat, filtres, mètrica i pestanyes) viu al hash de
 * l'URL perquè una vista concreta es pugui desar o compartir amb el mateix
 * enllaç privat. Totes les dades es pinten amb textContent: els valors com
 * referents o UTM venen de fora i mai no s'interpreten com a HTML.
 */
(function () {
    "use strict";

    var basePath = location.pathname.replace(/\/+$/, "") + "/";
    var numberFormat = new Intl.NumberFormat("ca");
    var decimalFormat = new Intl.NumberFormat("ca", { maximumFractionDigits: 1 });
    var regionNames = safeDisplayNames();
    var DAY_NAMES = ["Dl", "Dt", "Dc", "Dj", "Dv", "Ds", "Dg"];
    var MONTHS = ["gen.", "febr.", "març", "abr.", "maig", "juny", "jul.",
        "ag.", "set.", "oct.", "nov.", "des."];

    var KPIS = [
        { key: "visitors", label: "Visitants", fmt: formatInt, chart: true },
        { key: "sessions", label: "Sessions", fmt: formatInt, chart: true },
        { key: "pageviews", label: "Pàgines vistes", fmt: formatInt, chart: true },
        { key: "views_per_session", label: "Pàgines / sessió", fmt: formatDecimal },
        { key: "avg_session_duration_s", label: "Durada mitjana",
            fmt: formatDuration },
        { key: "bounce_rate", label: "Taxa de rebot", fmt: formatPct,
            inverse: true, chart: true, isRate: true },
        { key: "conversions", label: "Contactes", fmt: formatInt, chart: true },
        { key: "conversion_rate", label: "Taxa de conversió", fmt: formatPct,
            isRate: true }
    ];

    var SESSION_COLUMNS = [
        { key: "visitors", label: "Visitants", fmt: formatInt },
        { key: "sessions", label: "Sessions", fmt: formatInt },
        { key: "bounce_rate", label: "Rebot", fmt: formatPct },
        { key: "conversions", label: "Contactes", fmt: formatInt }
    ];
    var PAGE_COLUMNS = [
        { key: "pageviews", label: "Vistes", fmt: formatInt },
        { key: "visitors", label: "Visitants", fmt: formatInt },
        { key: "avg_time_on_page_s", label: "Temps", fmt: formatDuration },
        { key: "avg_scroll_pct", label: "Scroll", fmt: formatScroll }
    ];
    var ENTRY_COLUMNS = [
        { key: "sessions", label: "Entrades", fmt: formatInt },
        { key: "bounce_rate", label: "Rebot", fmt: formatPct },
        { key: "conversions", label: "Contactes", fmt: formatInt }
    ];

    var DIMENSION_LABELS = {
        path: "Pàgina", lang: "Idioma", channel: "Canal", source: "Font",
        referrer_host: "Domini", utm_source: "UTM origen", utm_medium: "UTM mitjà",
        utm_campaign: "Campanya", country: "País", region: "Regió",
        city: "Ciutat", device: "Dispositiu", browser: "Navegador", os: "Sistema"
    };

    var state = readState();
    var lastReport = null;
    var requestCounter = 0;

    /* ---------------------------------------------------------------- */
    /* Estat a l'URL                                                    */
    /* ---------------------------------------------------------------- */
    function readState() {
        var params = new URLSearchParams(location.hash.slice(1));
        var filters = {};
        params.forEach(function (value, key) {
            if (key.indexOf("f_") === 0) filters[key.slice(2)] = value;
        });
        var range = presetRange(params.get("preset") || "30d");
        return {
            preset: params.get("from") ? "" : (params.get("preset") || "30d"),
            from: params.get("from") || range.from,
            to: params.get("to") || range.to,
            interval: params.get("interval") || "auto",
            metric: params.get("metric") || "visitors",
            filters: filters,
            tabs: {}
        };
    }

    function writeState() {
        var params = new URLSearchParams();
        if (state.preset) {
            params.set("preset", state.preset);
        } else {
            params.set("from", state.from);
            params.set("to", state.to);
        }
        if (state.interval !== "auto") params.set("interval", state.interval);
        if (state.metric !== "visitors") params.set("metric", state.metric);
        Object.keys(state.filters).forEach(function (key) {
            params.set("f_" + key, state.filters[key]);
        });
        history.replaceState(null, "", "#" + params.toString());
    }

    function queryString(includeInterval) {
        var params = new URLSearchParams({ from: state.from, to: state.to });
        if (includeInterval) params.set("interval", state.interval);
        Object.keys(state.filters).forEach(function (key) {
            params.set("f_" + key, state.filters[key]);
        });
        return params.toString();
    }

    /* ---------------------------------------------------------------- */
    /* Dates                                                            */
    /* ---------------------------------------------------------------- */
    function isoDay(date) {
        var month = String(date.getMonth() + 1).padStart(2, "0");
        var day = String(date.getDate()).padStart(2, "0");
        return date.getFullYear() + "-" + month + "-" + day;
    }

    function shiftDays(date, days) {
        var copy = new Date(date);
        copy.setDate(copy.getDate() + days);
        return copy;
    }

    function presetRange(preset) {
        var today = new Date();
        switch (preset) {
            case "today":
                return { from: isoDay(today), to: isoDay(today) };
            case "yesterday":
                var yesterday = shiftDays(today, -1);
                return { from: isoDay(yesterday), to: isoDay(yesterday) };
            case "7d":
                return { from: isoDay(shiftDays(today, -6)), to: isoDay(today) };
            case "90d":
                return { from: isoDay(shiftDays(today, -89)), to: isoDay(today) };
            case "month":
                return { from: isoDay(new Date(today.getFullYear(),
                    today.getMonth(), 1)), to: isoDay(today) };
            case "lastmonth":
                return {
                    from: isoDay(new Date(today.getFullYear(),
                        today.getMonth() - 1, 1)),
                    to: isoDay(new Date(today.getFullYear(), today.getMonth(), 0))
                };
            case "12m":
                return { from: isoDay(new Date(today.getFullYear() - 1,
                    today.getMonth(), today.getDate() + 1)), to: isoDay(today) };
            default:
                return { from: isoDay(shiftDays(today, -29)), to: isoDay(today) };
        }
    }

    function formatDayLabel(isoDate) {
        var parts = isoDate.split("-");
        return Number(parts[2]) + " " + MONTHS[Number(parts[1]) - 1] + " " + parts[0];
    }

    function formatBucket(isoDateTime, interval, short) {
        var date = new Date(isoDateTime);
        var day = date.getDate() + " " + MONTHS[date.getMonth()];
        if (interval === "hour") {
            var hour = String(date.getHours()).padStart(2, "0") + ":00";
            return short ? hour : day + ", " + hour;
        }
        if (interval === "week") return (short ? "" : "Setmana del ") + day;
        if (interval === "month") return MONTHS[date.getMonth()] + " " +
            date.getFullYear();
        return short ? day : DAY_NAMES[(date.getDay() + 6) % 7] + " " + day +
            " " + date.getFullYear();
    }

    /* ---------------------------------------------------------------- */
    /* Formats                                                          */
    /* ---------------------------------------------------------------- */
    function formatInt(value) {
        return value === null || value === undefined ? "–" :
            numberFormat.format(value);
    }
    function formatDecimal(value) {
        return value === null || value === undefined ? "–" :
            decimalFormat.format(value);
    }
    function formatPct(value) {
        return value === null || value === undefined ? "–" :
            decimalFormat.format(value * 100) + " %";
    }
    function formatScroll(value) {
        return value === null || value === undefined ? "–" : Math.round(value) + " %";
    }
    function formatDuration(seconds) {
        if (seconds === null || seconds === undefined) return "–";
        var total = Math.round(seconds);
        if (total < 60) return total + " s";
        var minutes = Math.floor(total / 60);
        var rest = total % 60;
        if (minutes < 60) {
            return minutes + " min " + String(rest).padStart(2, "0") + " s";
        }
        return Math.floor(minutes / 60) + " h " + (minutes % 60) + " min";
    }

    function safeDisplayNames() {
        try {
            return new Intl.DisplayNames(["ca"], { type: "region" });
        } catch (err) {
            return null;
        }
    }

    function flagEmoji(code) {
        if (!/^[A-Z]{2}$/.test(code)) return "🌐";
        return String.fromCodePoint.apply(null, code.split("").map(function (c) {
            return 0x1f1a5 + c.charCodeAt(0);
        }));
    }

    function displayValue(dimension, value) {
        if (dimension === "country") {
            if (!value) return "🌐 Desconegut";
            var name = regionNames ? regionNames.of(value) : value;
            return flagEmoji(value) + " " + name;
        }
        if (dimension === "lang") {
            return { ca: "Català", es: "Castellà" }[value] || value || "Desconegut";
        }
        if (dimension === "path" || dimension === "pages" ||
                dimension === "entry_pages") {
            if (value === "/") return "/ · Inici (català)";
            if (value === "/es/") return "/es/ · Inicio (castellà)";
            return value;
        }
        if (!value) {
            if (dimension.indexOf("utm_") === 0) return "(sense campanya)";
            if (dimension === "referrer_host") return "(cap · directe)";
            return "Desconegut";
        }
        return value;
    }

    /* ---------------------------------------------------------------- */
    /* DOM                                                              */
    /* ---------------------------------------------------------------- */
    function el(tag, attributes, children) {
        var node = document.createElement(tag);
        Object.keys(attributes || {}).forEach(function (key) {
            if (key === "text") node.textContent = attributes[key];
            else if (key === "className") node.className = attributes[key];
            else node.setAttribute(key, attributes[key]);
        });
        (children || []).forEach(function (child) {
            if (child) node.appendChild(child);
        });
        return node;
    }

    function svg(tag, attributes) {
        var node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.keys(attributes || {}).forEach(function (key) {
            node.setAttribute(key, attributes[key]);
        });
        return node;
    }

    function showToast(message) {
        var toast = document.getElementById("toast");
        toast.textContent = message;
        toast.hidden = false;
        clearTimeout(showToast.timer);
        showToast.timer = setTimeout(function () { toast.hidden = true; }, 5000);
    }

    /* ---------------------------------------------------------------- */
    /* Càrrega de dades                                                 */
    /* ---------------------------------------------------------------- */
    function load() {
        writeState();
        syncControls();
        var requestId = ++requestCounter;
        var content = document.querySelector(".content");
        content.classList.add("loading");

        fetch(basePath + "report?" + queryString(true), {
            headers: { Accept: "application/json" },
            cache: "no-store"
        })
            .then(function (response) {
                return response.json().then(function (body) {
                    if (!response.ok) {
                        throw new Error((body.error && body.error.message) ||
                            "Error " + response.status);
                    }
                    return body;
                });
            })
            .then(function (report) {
                if (requestId !== requestCounter) return;
                lastReport = report;
                render(report);
            })
            .catch(function (error) {
                showToast("No s'han pogut carregar les dades: " + error.message);
            })
            .finally(function () {
                if (requestId === requestCounter) content.classList.remove("loading");
            });
    }

    function loadRealtime() {
        fetch(basePath + "realtime", { cache: "no-store" })
            .then(function (response) { return response.ok ? response.json() : null; })
            .then(function (data) {
                if (!data) return;
                document.getElementById("live-count").textContent =
                    formatInt(data.active_visitors) +
                    (data.active_visitors === 1 ? " visitant" : " visitants");
                document.getElementById("live").title = data.pages.length ?
                    "Ara mateix: " + data.pages.map(function (page) {
                        return page.value + " (" + page.visitors + ")";
                    }).join(", ") : "Cap visitant als últims 5 minuts";
            })
            .catch(function () { /* el temps real és accessori */ });
    }

    /* ---------------------------------------------------------------- */
    /* Pintat                                                           */
    /* ---------------------------------------------------------------- */
    function render(report) {
        var range = report.range;
        document.getElementById("period").textContent =
            formatDayLabel(range.from) + " – " + formatDayLabel(range.to) +
            "  ·  comparat amb " + formatDayLabel(range.previous_from) + " – " +
            formatDayLabel(range.previous_to) + "  ·  hora de " + range.timezone;
        renderKpis(report.kpis);
        renderChart(report);
        renderLists(report);
        renderHeatmap(report.heatmap);
        renderFilters();
    }

    function renderKpis(kpis) {
        var container = document.getElementById("kpis");
        container.replaceChildren();
        KPIS.forEach(function (kpi) {
            var current = kpis.current[kpi.key];
            var previous = kpis.previous[kpi.key];
            var card = el("button", {
                type: "button",
                className: "kpi" + (state.metric === kpi.key ? " active" : ""),
                title: kpi.chart ? "Mostra l'evolució al gràfic" : ""
            }, [
                el("span", { className: "kpi-label", text: kpi.label }),
                el("span", { className: "kpi-value", text: kpi.fmt(current) }),
                deltaBadge(current, previous, kpi),
                el("span", { className: "kpi-prev",
                    text: "abans: " + kpi.fmt(previous) })
            ]);
            if (kpi.chart) {
                card.addEventListener("click", function () {
                    state.metric = kpi.key;
                    writeState();
                    renderKpis(lastReport.kpis);
                    renderChart(lastReport);
                });
            } else {
                card.style.cursor = "default";
            }
            container.appendChild(card);
        });
    }

    function deltaBadge(current, previous, kpi) {
        if (current === null || current === undefined || previous === null ||
                previous === undefined) {
            return el("span", { className: "delta flat", text: "sense comparació" });
        }
        var diff;
        var text;
        if (kpi.isRate) {
            diff = (current - previous) * 100;
            text = (diff >= 0 ? "+" : "−") +
                decimalFormat.format(Math.abs(diff)) + " pp";
        } else if (previous === 0) {
            diff = current > 0 ? 1 : 0;
            text = current > 0 ? "nou" : "=";
        } else {
            diff = (current - previous) / previous * 100;
            text = (diff >= 0 ? "▲ " : "▼ ") +
                decimalFormat.format(Math.abs(diff)) + " %";
        }
        if (Math.abs(diff) < 0.05) {
            return el("span", { className: "delta flat", text: "= sense canvis" });
        }
        var isGood = kpi.inverse ? diff < 0 : diff > 0;
        return el("span", { className: "delta " + (isGood ? "up" : "down"),
            text: text });
    }

    /* Màxim de l'eix amb 4 trams "rodons" (1, 2, 5 × 10^n), mai decimals */
    function niceMax(value) {
        var rawStep = Math.max(value, 1) / 4;
        var magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
        var step = [1, 2, 5, 10].map(function (factor) {
            return factor * magnitude;
        }).filter(function (candidate) { return candidate >= rawStep; })[0];
        return Math.max(1, Math.ceil(step)) * 4;
    }

    function renderChart(report) {
        var kpi = KPIS.filter(function (item) {
            return item.key === state.metric;
        })[0] || KPIS[0];
        document.getElementById("chart-title").textContent = kpi.label;
        var container = document.getElementById("chart");
        container.replaceChildren();

        var series = report.timeseries;
        var previous = report.previous_timeseries;
        var interval = report.range.interval;
        var width = container.clientWidth || 800;
        var height = container.clientHeight || 280;
        var pad = { top: 12, right: 14, bottom: 28, left: 46 };
        var innerWidth = width - pad.left - pad.right;
        var innerHeight = height - pad.top - pad.bottom;

        function valueAt(list, index) {
            var point = list[index];
            return point ? point[kpi.key] : null;
        }
        var allValues = series.map(function (_, i) { return valueAt(series, i); })
            .concat(series.map(function (_, i) { return valueAt(previous, i); }))
            .filter(function (v) { return v !== null && v !== undefined; });
        var maxY = kpi.isRate ? 1 :
            niceMax(Math.max.apply(null, allValues.concat([0])));
        var step = series.length > 1 ? innerWidth / (series.length - 1) : 0;

        function x(index) {
            return pad.left + (series.length > 1 ? index * step : innerWidth / 2);
        }
        function y(value) {
            return pad.top + innerHeight - (value / maxY) * innerHeight;
        }

        var root = svg("svg", { viewBox: "0 0 " + width + " " + height,
            role: "img", "aria-label": "Evolució de " + kpi.label });
        var defs = svg("defs");
        var gradient = svg("linearGradient", { id: "area-gradient", x1: 0, y1: 0,
            x2: 0, y2: 1 });
        gradient.appendChild(svg("stop", { offset: "0%", "stop-color": "#7cccaf",
            "stop-opacity": "0.35" }));
        gradient.appendChild(svg("stop", { offset: "100%", "stop-color": "#7cccaf",
            "stop-opacity": "0" }));
        defs.appendChild(gradient);
        root.appendChild(defs);

        for (var tick = 0; tick <= 4; tick++) {
            var tickValue = maxY * tick / 4;
            var tickY = y(tickValue);
            root.appendChild(svg("line", { x1: pad.left, x2: width - pad.right,
                y1: tickY, y2: tickY, "class": "grid-line" }));
            var tickLabel = svg("text", { x: pad.left - 8, y: tickY + 4,
                "text-anchor": "end", "class": "axis-label" });
            tickLabel.textContent = kpi.isRate ? Math.round(tickValue * 100) + "%" :
                formatInt(Math.round(tickValue * 10) / 10);
            root.appendChild(tickLabel);
        }

        var labelEvery = Math.max(1, Math.ceil(series.length / Math.max(2,
            Math.floor(innerWidth / 90))));
        series.forEach(function (point, index) {
            if (index % labelEvery !== 0) return;
            var label = svg("text", { x: x(index), y: height - 8,
                "text-anchor": "middle", "class": "axis-label" });
            label.textContent = formatBucket(point.t, interval, true);
            root.appendChild(label);
        });

        function linePath(list) {
            var path = "";
            var penDown = false;
            series.forEach(function (_, index) {
                var value = valueAt(list, index);
                if (value === null || value === undefined) {
                    penDown = false;
                    return;
                }
                path += (penDown ? " L" : " M") + x(index).toFixed(1) + " " +
                    y(value).toFixed(1);
                penDown = true;
            });
            return path.trim();
        }

        var previousPath = linePath(previous);
        if (previousPath) {
            root.appendChild(svg("path", { d: previousPath,
                "class": "line-previous" }));
        }
        var currentPath = linePath(series);
        if (currentPath && !kpi.isRate) {
            root.appendChild(svg("path", {
                d: currentPath + " L" + x(series.length - 1) + " " + y(0) +
                    " L" + x(0) + " " + y(0) + " Z",
                "class": "area"
            }));
        }
        if (currentPath) {
            root.appendChild(svg("path", { d: currentPath, "class": "line-current" }));
        }

        var hoverLine = svg("line", { y1: pad.top, y2: pad.top + innerHeight,
            "class": "hover-line", visibility: "hidden" });
        var hoverDot = svg("circle", { r: 4, "class": "dot", visibility: "hidden" });
        root.appendChild(hoverLine);
        root.appendChild(hoverDot);

        var overlay = svg("rect", { x: pad.left, y: pad.top, width: innerWidth,
            height: innerHeight, fill: "transparent" });
        var tooltip = document.getElementById("tooltip");
        overlay.addEventListener("mousemove", function (event) {
            var bounds = root.getBoundingClientRect();
            var scale = width / bounds.width;
            var localX = (event.clientX - bounds.left) * scale;
            var index = step ? Math.round((localX - pad.left) / step) : 0;
            index = Math.max(0, Math.min(series.length - 1, index));
            var value = valueAt(series, index);
            var previousValue = valueAt(previous, index);
            hoverLine.setAttribute("x1", x(index));
            hoverLine.setAttribute("x2", x(index));
            hoverLine.setAttribute("visibility", "visible");
            if (value !== null && value !== undefined) {
                hoverDot.setAttribute("cx", x(index));
                hoverDot.setAttribute("cy", y(value));
                hoverDot.setAttribute("visibility", "visible");
            }
            tooltip.replaceChildren(
                el("strong", { text: formatBucket(series[index].t, interval, false) }),
                el("div", { text: kpi.label + ": " + kpi.fmt(value) }),
                el("div", { text: previous[index] ? "Període anterior (" +
                    formatBucket(previous[index].t, interval, true) + "): " +
                    kpi.fmt(previousValue) : "Període anterior: –" })
            );
            tooltip.hidden = false;
            tooltip.style.left = Math.min(event.clientX + 14,
                window.innerWidth - tooltip.offsetWidth - 10) + "px";
            tooltip.style.top = (event.clientY + 14) + "px";
        });
        overlay.addEventListener("mouseleave", function () {
            tooltip.hidden = true;
            hoverLine.setAttribute("visibility", "hidden");
            hoverDot.setAttribute("visibility", "hidden");
        });
        root.appendChild(overlay);
        container.appendChild(root);
    }

    function activeDimension(panel) {
        var fixed = panel.querySelector("[data-list]");
        if (fixed) return fixed.getAttribute("data-list");
        var active = panel.querySelector("[data-tabs] .active");
        return active ? active.getAttribute("data-dim") : null;
    }

    function renderLists(report) {
        document.querySelectorAll("[data-panel]").forEach(function (panel) {
            var dimension = activeDimension(panel);
            var list = panel.querySelector(".list");
            var rows;
            var columns;
            var filterKey = dimension;
            if (dimension === "pages") {
                rows = report.pages;
                columns = PAGE_COLUMNS;
                filterKey = "path";
            } else if (dimension === "entry_pages") {
                rows = report.entry_pages;
                columns = ENTRY_COLUMNS;
                filterKey = "path";
            } else {
                rows = report.breakdowns[dimension] || [];
                columns = SESSION_COLUMNS;
            }
            renderList(list, dimension, filterKey, rows, columns);
        });
    }

    function renderList(container, dimension, filterKey, rows, columns) {
        container.replaceChildren();
        container.style.setProperty("--cols", columns.length);
        if (!rows.length) {
            container.appendChild(el("div", { className: "empty",
                text: "Encara no hi ha dades en aquest període." }));
            return;
        }
        var header = el("div", { className: "list-header" },
            [el("span", { text: DIMENSION_LABELS[filterKey] || "" })].concat(
                columns.map(function (column) {
                    return el("span", { text: column.label });
                })));
        header.style.setProperty("--cols", columns.length);
        var body = el("div", { className: "list-body" });
        var barKey = columns[0].key;
        var maxValue = Math.max.apply(null, rows.map(function (row) {
            return row[barKey] || 0;
        })) || 1;

        rows.forEach(function (row) {
            var label = displayValue(dimension, row.value);
            var bar = el("span", { className: "bar" });
            bar.style.width = Math.max(2, (row[barKey] || 0) / maxValue * 100) + "%";
            var item = el("div", {
                className: "row",
                role: "button",
                tabindex: "0",
                title: "Filtra per " +
                    (DIMENSION_LABELS[filterKey] || "").toLowerCase() + ": " + label
            }, [bar, el("span", { className: "label", text: label })].concat(
                columns.map(function (column) {
                    return el("span", { text: column.fmt(row[column.key]) });
                })));
            item.style.setProperty("--cols", columns.length);
            function applyFilter() {
                state.filters[filterKey] = row.value;
                load();
            }
            item.addEventListener("click", applyFilter);
            item.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    applyFilter();
                }
            });
            body.appendChild(item);
        });
        container.appendChild(header);
        container.appendChild(body);
    }

    function renderHeatmap(matrix) {
        var container = document.getElementById("heatmap");
        container.replaceChildren();
        var maxValue = Math.max.apply(null, matrix.map(function (row) {
            return Math.max.apply(null, row);
        })) || 1;
        container.appendChild(el("span"));
        for (var hour = 0; hour < 24; hour++) {
            container.appendChild(el("span", { className: "hour",
                text: hour % 3 === 0 ? String(hour) : "" }));
        }
        matrix.forEach(function (row, dayIndex) {
            container.appendChild(el("span", { className: "day",
                text: DAY_NAMES[dayIndex] }));
            row.forEach(function (value, hourIndex) {
                var cell = el("span", {
                    className: "cell",
                    title: DAY_NAMES[dayIndex] + " " + hourIndex + ":00–" +
                        (hourIndex + 1) + ":00 · " + formatInt(value) + " sessions"
                });
                if (value) {
                    var intensity = 0.12 + 0.88 * value / maxValue;
                    cell.style.background = "rgba(74, 169, 140, " +
                        intensity.toFixed(2) + ")";
                }
                container.appendChild(cell);
            });
        });
    }

    function renderFilters() {
        var container = document.getElementById("filters");
        container.replaceChildren();
        var keys = Object.keys(state.filters);
        container.hidden = !keys.length;
        if (!keys.length) return;
        container.appendChild(el("span", { text: "Filtres:" }));
        keys.forEach(function (key) {
            var remove = el("button", { type: "button", "aria-label": "Treu el filtre",
                text: "×" });
            remove.addEventListener("click", function () {
                delete state.filters[key];
                load();
            });
            container.appendChild(el("span", { className: "chip" }, [
                el("span", { text: (DIMENSION_LABELS[key] || key) + ": " +
                    displayValue(key, state.filters[key]) }),
                remove
            ]));
        });
        var clear = el("button", { type: "button", className: "chip-clear",
            text: "Treu-los tots" });
        clear.addEventListener("click", function () {
            state.filters = {};
            load();
        });
        container.appendChild(clear);
    }

    /* ---------------------------------------------------------------- */
    /* Controls                                                         */
    /* ---------------------------------------------------------------- */
    function syncControls() {
        document.querySelectorAll("[data-preset]").forEach(function (button) {
            button.classList.toggle("active",
                button.getAttribute("data-preset") === state.preset);
        });
        document.getElementById("from").value = state.from;
        document.getElementById("to").value = state.to;
        document.getElementById("interval").value = state.interval;
        document.getElementById("export").href = basePath + "export.csv?" +
            queryString(false);
    }

    document.querySelectorAll("[data-preset]").forEach(function (button) {
        button.addEventListener("click", function () {
            state.preset = button.getAttribute("data-preset");
            var range = presetRange(state.preset);
            state.from = range.from;
            state.to = range.to;
            load();
        });
    });

    ["from", "to"].forEach(function (id) {
        document.getElementById(id).addEventListener("change", function (event) {
            if (!event.target.value) return;
            state[id] = event.target.value;
            state.preset = "";
            load();
        });
    });

    document.getElementById("interval").addEventListener("change", function (event) {
        state.interval = event.target.value;
        load();
    });

    document.querySelectorAll("[data-tabs]").forEach(function (tabs) {
        tabs.addEventListener("click", function (event) {
            var button = event.target.closest("button");
            if (!button) return;
            tabs.querySelectorAll("button").forEach(function (other) {
                other.classList.toggle("active", other === button);
            });
            if (lastReport) renderLists(lastReport);
        });
    });

    var ignoreCheckbox = document.getElementById("ignore-me");
    try {
        ignoreCheckbox.checked = localStorage.getItem("jc-analytics-ignore") === "1";
        ignoreCheckbox.addEventListener("change", function () {
            if (ignoreCheckbox.checked) {
                localStorage.setItem("jc-analytics-ignore", "1");
            } else {
                localStorage.removeItem("jc-analytics-ignore");
            }
        });
    } catch (err) {
        ignoreCheckbox.disabled = true;
    }

    var resizeTimer;
    window.addEventListener("resize", function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            if (lastReport) renderChart(lastReport);
        }, 150);
    });

    /* Enganxar un altre enllaç de vista a la mateixa pestanya */
    window.addEventListener("hashchange", function () {
        state = readState();
        load();
    });

    load();
    loadRealtime();
    setInterval(loadRealtime, 30000);
})();
