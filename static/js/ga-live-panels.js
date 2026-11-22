/**
 * Auto-refresh Gram rate + campaign stats on page load.
 * Shows the premium live overlay while remote sync runs.
 */
(function () {
  "use strict";

  function csrfToken() {
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input && input.value) return input.value;
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function ensureOverlay() {
    var el = document.getElementById("ga-live-overlay");
    if (el) return el;
    el = document.createElement("div");
    el.id = "ga-live-overlay";
    el.className = "ga-live-overlay";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.setAttribute("aria-hidden", "true");
    el.innerHTML =
      '<div class="ga-live-loader">' +
      '<div class="ga-live-loader__orbit" aria-hidden="true">' +
      '<span class="ga-live-loader__ring"></span>' +
      '<span class="ga-live-loader__ring ga-live-loader__ring--soft"></span>' +
      '<span class="ga-live-loader__core"></span>' +
      "</div>" +
      '<p class="ga-live-loader__title" data-ga-live-title>در حال دریافت دادهٔ لحظه‌ای</p>' +
      '<p class="ga-live-loader__text" data-ga-live-text>نرخ گرام و آمار کمپین در حال همگام‌سازی است</p>' +
      '<div class="ga-live-loader__bars" aria-hidden="true"><span></span><span></span><span></span></div>' +
      "</div>";
    document.body.appendChild(el);
    return el;
  }

  function showLoader(title, text) {
    var el = ensureOverlay();
    var t = el.querySelector("[data-ga-live-title]");
    var d = el.querySelector("[data-ga-live-text]");
    if (t && title) t.textContent = title;
    if (d && text) d.textContent = text;
    el.classList.add("is-active");
    el.setAttribute("aria-hidden", "false");
  }

  function hideLoader() {
    var el = document.getElementById("ga-live-overlay");
    if (!el) return;
    el.classList.remove("is-active");
    el.setAttribute("aria-hidden", "true");
  }

  function reloadKey() {
    return "ga-live-reloaded:" + location.pathname + location.search;
  }

  async function fetchRate(url) {
    if (!url) return null;
    var res = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "text/html", "X-Requested-With": "XMLHttpRequest" },
    });
    if (!res.ok) return null;
    return res.text();
  }

  async function fetchStats(url, campaignId) {
    if (!url) return null;
    var body = new URLSearchParams();
    if (campaignId) body.set("campaign_id", campaignId);
    var res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: body.toString(),
    });
    if (!res.ok) return null;
    return res.json();
  }

  function applyRateHtml(html) {
    if (!html) return;
    document.querySelectorAll("[data-ga-live-rate]").forEach(function (node) {
      node.innerHTML = html;
      node.classList.remove("is-syncing");
    });
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  function markPanelsSyncing(on) {
    document.querySelectorAll("[data-ga-live-panel]").forEach(function (node) {
      node.classList.toggle("is-syncing", !!on);
    });
  }

  async function boot() {
    var root = document.querySelector("[data-ga-live-boot]");
    if (!root) return;

    var rateUrl = root.getAttribute("data-ga-live-rate-url") || "";
    var statsUrl = root.getAttribute("data-ga-live-stats-url") || "";
    var campaignId = root.getAttribute("data-ga-live-campaign-id") || "";
    var needsStats = !!statsUrl;
    var justReloaded = sessionStorage.getItem(reloadKey()) === "1";

    if (justReloaded) {
      sessionStorage.removeItem(reloadKey());
      if (rateUrl) {
        try {
          var htmlOnly = await fetchRate(rateUrl);
          applyRateHtml(htmlOnly);
        } catch (e) {
          /* keep server-rendered rate */
        }
      }
      return;
    }

    var title = needsStats
      ? "در حال دریافت دادهٔ لحظه‌ای"
      : "در حال دریافت نرخ گرام";
    var text = needsStats
      ? "نرخ گرام و آمار کمپین در حال همگام‌سازی است"
      : "نرخ لحظه‌ای گرام از بازار در حال به‌روزرسانی است";

    showLoader(title, text);
    markPanelsSyncing(true);

    var statsPayload = null;
    try {
      var tasks = [];
      if (rateUrl) tasks.push(fetchRate(rateUrl));
      else tasks.push(Promise.resolve(null));
      if (needsStats) tasks.push(fetchStats(statsUrl, campaignId));
      else tasks.push(Promise.resolve(null));

      var results = await Promise.all(tasks);
      applyRateHtml(results[0]);
      statsPayload = results[1];

      if (statsPayload && Number(statsPayload.refreshed) > 0) {
        sessionStorage.setItem(reloadKey(), "1");
        location.reload();
        return;
      }
    } catch (err) {
      /* keep cached UI */
    } finally {
      markPanelsSyncing(false);
      hideLoader();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.GramAdsLive = {
    show: showLoader,
    hide: hideLoader,
  };
})();
