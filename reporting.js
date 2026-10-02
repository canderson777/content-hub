/* Reporting view: verified, read-only sources only.
 * The server holds the read-only GSC token; this page only talks to the
 * local API. No external fetches, no paid data, no invented figures. */
(function () {
  "use strict";

  const STATUS_LABELS = {
    verified: "Verified · read-only access connected",
    account_available: "Account exists · no read-only connection yet",
    not_connected: "Not connected",
  };
  const KIND_LABELS = {
    gsc: "Search Console",
    site: "Website",
    social: "Social",
    newsletter: "Newsletter",
    store: "Store",
  };

  function fmtNumber(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const n = Number(value);
    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "K";
    return String(Math.round(n));
  }

  function fmtCtr(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return (Number(value) * 100).toFixed(2) + "%";
  }

  function fmtPosition(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return Number(value).toFixed(1);
  }

  function statusNode(scope, source) {
    const row = document.createElement("div");
    row.className = "reporting-source " + source.status;
    const dot = document.createElement("span");
    dot.className = "rs-dot";
    const body = document.createElement("div");
    const kind = document.createElement("div");
    kind.className = "rs-kind";
    kind.textContent = KIND_LABELS[source.kind] || source.kind;
    const label = document.createElement("div");
    label.className = "rs-label";
    label.textContent = source.label;
    const desc = document.createElement("div");
    desc.className = "rs-desc";
    desc.textContent = (STATUS_LABELS[source.status] || source.status) + (source.description ? " — " + source.description : "");
    body.append(kind, label, desc);

    if (source.status === "verified" && source.kind === "gsc" && scope.gsc && scope.gsc.property === source.property) {
      const m = scope.gsc.metrics || {};
      const metrics = document.createElement("div");
      metrics.className = "rs-metrics";
      metrics.textContent =
        fmtNumber(m.clicks) + " clicks · " +
        fmtNumber(m.impressions) + " impressions · CTR " +
        fmtCtr(m.ctr) + " · avg position " +
        fmtPosition(m.averagePosition);
      const window = document.createElement("div");
      window.className = "rs-window";
      window.textContent =
        "Window " + (scope.gsc.window ? scope.gsc.window.startDate + " → " + scope.gsc.window.endDate : "") +
        " · permission " + (scope.gsc.permission || "") + " · source Google Search Console (read-only)";
      body.append(metrics, window);
    }

    if (source.status === "verified" && source.kind === "pagespeed") {
      const scores = scope.pagespeed && scope.pagespeed.scores;
      if (scores) {
        const metrics = document.createElement("div");
        metrics.className = "rs-metrics";
        metrics.textContent =
          "Performance " + (scores.performance != null ? scores.performance : "—") +
          " · Accessibility " + (scores.accessibility != null ? scores.accessibility : "—") +
          " · Best practices " + (scores["best-practices"] != null ? scores["best-practices"] : "—") +
          " · SEO " + (scores.seo != null ? scores.seo : "—");
        const window = document.createElement("div");
        window.className = "rs-window";
        window.textContent = "PageSpeed Insights (free) · " + (scope.pagespeed.strategy || "mobile") + " · source Google PageSpeed";
        body.append(metrics, window);
      } else {
        const note = document.createElement("div");
        note.className = "rs-desc";
        note.textContent = "PageSpeed score not available right now (free shared quota may be busy).";
        body.append(note);
      }
    }

    if (source.status === "verified" && source.kind === "newsletter" && scope.mailerlite) {
      const g = scope.mailerlite.groups && scope.mailerlite.groups[0];
      if (g) {
        const metrics = document.createElement("div");
        metrics.className = "rs-metrics";
        metrics.textContent =
          fmtNumber(g.sent_count) + " sent · " +
          fmtNumber(g.opens_count) + " opens (" + fmtPct(g.open_rate) + ") · " +
          fmtNumber(g.click_count) + " clicks (" + fmtPct(g.click_rate) + ")";
        const window = document.createElement("div");
        window.className = "rs-window";
        window.textContent = (g.name || "Newsletter") + " · " + fmtNumber(g.active_count) + " active subscribers · source MailerLite (read-only)";
        body.append(metrics, window);
      }
    }

    row.append(dot, body);
    return row;
  }

  function fmtPct(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return (Number(value) * 100).toFixed(2) + "%";
  }

  function buildBrandCard(brandId, label, sources, scope) {
    const card = document.createElement("section");
    card.className = "reporting-brand";
    card.dataset.brand = brandId;
    const h = document.createElement("h3");
    h.textContent = label;
    const sub = document.createElement("div");
    sub.className = "rb-sub";
    sub.textContent = brandId;
    card.append(h, sub);
    (sources || []).forEach(function (source) {
      card.append(statusNode(scope || {}, source));
    });
    return card;
  }

  function setStatus(message, isError) {
    const el = document.getElementById("reportingStatus");
    if (!el) return;
    el.textContent = message;
    el.className = "reporting-status" + (isError ? " error" : "");
  }

  async function fetchJson(endpoint) {
    const response = await fetch(endpoint, { cache: "no-store" });
    const body = await response.json().catch(function () { return {}; });
    return { ok: response.ok, status: response.status, body: body };
  }

  async function refresh() {
    const listEl = document.getElementById("reportingSources");
    const brandSelect = document.getElementById("activeBrandSelect");
    if (!listEl || !brandSelect) return;
    const brandId = brandSelect.value;
    setStatus("Loading source inventory…");
    listEl.innerHTML = "";
    try {
      const sourcesResponse = await fetch("/api/reporting/sources", { cache: "no-store" });
      const sourcesPayload = await sourcesResponse.json();
      if (!sourcesResponse.ok) throw new Error(sourcesPayload.error || "Could not load source inventory.");

      const scope = {};
      const brandSources = sourcesPayload.sources[brandId];
      if (brandSources) {
        const kinds = brandSources.map(function (s) { return s.kind; });
        if (kinds.includes("gsc")) {
          const gscResponse = await fetchJson("/api/reporting/gsc?brand=" + encodeURIComponent(brandId));
          if (gscResponse.ok) {
            scope.gsc = gscResponse.body;
          } else {
            setStatus("Search Console is available but the read failed: " + (gscResponse.body.error || gscResponse.status), true);
          }
        }
        if (kinds.includes("pagespeed")) {
          const psResponse = await fetchJson("/api/reporting/pagespeed?brand=" + encodeURIComponent(brandId));
          if (psResponse.ok) {
            scope.pagespeed = psResponse.body;
          } else if (psResponse.status === 429) {
            scope.pagespeed = null; // honest quota state handled below
          } else {
            setStatus("PageSpeed could not answer right now.", true);
          }
        }
        if (kinds.includes("newsletter") && brandId === "brand-a") {
          const mlResponse = await fetchJson("/api/reporting/mailerlite?brand=" + encodeURIComponent(brandId));
          if (mlResponse.ok) {
            scope.mailerlite = mlResponse.body;
          } else if (mlResponse.status !== 503) {
            // 503 = not connected; leave the honest source row without metrics.
            setStatus("MailerLite is available but the read failed: " + (mlResponse.body.error || mlResponse.status), true);
          }
        }
      }

      const order = ["brand-a", "brand-b", "brand-c"];
      Object.keys(sourcesPayload.sources || {}).sort(function (a, b) {
        return order.indexOf(a) - order.indexOf(b);
      }).forEach(function (id) {
        const sources = sourcesPayload.sources[id] || [];
        const labelEl = brandSelect.querySelector('option[value="' + id + '"]');
        const label = labelEl ? labelEl.textContent : id;
        if (id === brandId) {
          listEl.append(buildBrandCard(id, label + " · selected", sources, scope));
        } else {
          listEl.append(buildBrandCard(id, label, sources, null));
        }
      });
      setStatus("Showing only verified read-only sources. No paid data is used.");
    } catch (error) {
      setStatus(error.message || "Could not load reporting sources.", true);
    }
  }

  const brandSelect = document.getElementById("activeBrandSelect");
  if (brandSelect) {
    brandSelect.addEventListener("change", function () {
      if (document.getElementById("reporting").classList.contains("on")) refresh();
    });
  }

  window.Reporting = { refresh: refresh };
})();