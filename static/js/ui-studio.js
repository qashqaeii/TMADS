/* Approximate, local-only preview; no requests and no markup injection. */
(function () {
  "use strict";
  function boot() {
    var panel = document.getElementById("studio-preview-panel");
    var form = document.querySelector(".studio-form");
    if (!panel || !form) return;
    function value(name, fallback) {
      var el = form.querySelector('[name="' + name + '"]');
      return el ? el.value : fallback;
    }
    function fill(selector, text) {
      var el = panel.querySelector(selector);
      if (el) el.textContent = text;
    }
    function update() {
      var selected = form.querySelector('[name="target_type"]:checked');
      var kind = selected ? selected.value : panel.dataset.previewType;
      var search = kind === "search";
      panel.querySelector("[data-preview-search]").hidden = !search;
      panel.querySelector("[data-preview-message]").hidden = search;
      fill("[data-preview-mode]", search ? "جستجوی تلگرام" : kind === "bots" ? "بنر ربات" : "پیام اسپانسری");
      fill("[data-preview-title]", value("campaign_name", panel.dataset.previewName) || "عنوان تبلیغ");
      fill("[data-preview-url]", value("destination", panel.dataset.previewDestination) || "t.me/...");
      fill("[data-preview-copy]", value("ad_text", panel.dataset.previewText) || "متن تبلیغ شما");
      fill("[data-preview-button]", value("cta_label", panel.dataset.previewCta) || "مشاهده");
      var queries = form.querySelector('[name="search_queries_json"]');
      if (queries) {
        try { var items=JSON.parse(queries.value); fill("[data-preview-query]", Array.isArray(items) && items.length ? String(items[0]) : "جستجو"); } catch (_) {}
      }
    }
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
