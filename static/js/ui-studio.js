/* Local-only Telegram preview; safe text rendering and no extra requests. */
(function () {
  "use strict";

  function boot() {
    var panel = document.getElementById("studio-preview-panel");
    var form = document.getElementById("campaign-studio-form");
    if (!panel || !form) return;
    var targetLabels = {
      search: "نتایج جستجو",
      bots: "ربات‌های منتخب",
      users: "کاربران هدف",
      channels: "کانال‌های تلگرام"
    };
    var stepGuidance = {
      "1": "روش نمایش و مقصد مناسب را انتخاب کنید.",
      "2": "مخاطب را دقیق و متناسب با هدف کمپین تعریف کنید.",
      "3": "پیام کوتاه و روشن، شانس دیده‌شدن را بیشتر می‌کند.",
      "4": "پیش‌فاکتور قطعی در مرحله بازبینی نمایش داده می‌شود.",
      "5": "اطلاعات و قوانین را پیش از پرداخت بررسی کنید."
    };
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
      var searchPreview = panel.querySelector("[data-preview-search]");
      var messagePreview = panel.querySelector("[data-preview-message]");
      if (searchPreview) searchPreview.hidden = !search;
      if (messagePreview) messagePreview.hidden = search;
      var targetLabel = targetLabels[kind] || "تبلیغ در تلگرام";
      var campaignName = value("campaign_name", panel.dataset.previewName) || "عنوان تبلیغ";
      var destination = value("destination", panel.dataset.previewDestination) || "هنوز مشخص نشده";
      var adText = value("ad_text", panel.dataset.previewText) || "متن تبلیغ شما";
      var cta = value("cta_label", panel.dataset.previewCta) || "مشاهده";
      fill("[data-preview-mode]", targetLabel);
      fill("[data-preview-target-label]", targetLabel);
      fill("[data-preview-title]", campaignName);
      fill("[data-preview-campaign-name]", campaignName);
      fill("[data-preview-url]", destination);
      fill("[data-preview-destination-text]", destination);
      fill("[data-preview-copy]", adText);
      fill("[data-preview-button]", cta);
      var step = String(form.dataset.studioStep || panel.dataset.previewStep || "1");
      fill("[data-preview-guidance]", stepGuidance[step] || stepGuidance["1"]);
      var queries = form.querySelector('[name="search_queries_json"]');
      if (queries) {
        try {
          var items = JSON.parse(queries.value);
          fill("[data-preview-query]", Array.isArray(items) && items.length ? String(items[0]) : "جستجو");
        } catch (_) {
          fill("[data-preview-query]", "جستجو");
        }
      }
    }
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
