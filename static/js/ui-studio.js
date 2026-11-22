/* Local-only Telegram Ads-style preview; safe text rendering and no extra requests. */
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
      "1": "روش نمایش و مقصد را انتخاب کنید.",
      "2": "مخاطب هدف را مشخص کنید.",
      "3": "متن کوتاه و واضح بنویسید.",
      "4": "بودجه و زمان را تنظیم کنید.",
      "5": "قبل از پرداخت یک‌بار مرور کنید."
    };

    function value(name, fallback) {
      var el = form.querySelector('[name="' + name + '"]');
      return el ? el.value : fallback;
    }

    function checked(name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (!el) return panel.dataset.previewShowUserpic === "1";
      return !!el.checked;
    }

    function fill(selector, text) {
      panel.querySelectorAll(selector).forEach(function (el) {
        el.textContent = text;
      });
    }

    function brandFromDestination(destination, fallback) {
      var raw = String(destination || "").trim();
      if (!raw || raw === "هنوز مشخص نشده") return fallback || "عنوان تبلیغ";
      var match = raw.match(/(?:t\.me|telegram\.me)\/([A-Za-z0-9_]{3,64})/i);
      if (match) {
        var username = match[1];
        if (/bot$/i.test(username) && username.length > 3) {
          return username.replace(/bot$/i, "") || username;
        }
        return username;
      }
      if (raw.charAt(0) === "@") return raw.slice(1);
      return fallback || raw;
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
      var brand = brandFromDestination(destination, campaignName);
      var showPic = checked("show_userpic");

      fill("[data-preview-mode]", targetLabel);
      fill("[data-preview-target-label]", targetLabel);
      fill("[data-preview-title]", brand);
      fill("[data-preview-brand]", brand);
      fill("[data-preview-campaign-name]", campaignName);
      fill("[data-preview-url]", destination);
      fill("[data-preview-destination-text]", destination);
      fill("[data-preview-copy]", adText);

      panel.querySelectorAll("[data-preview-avatar]").forEach(function (avatar) {
        if (avatar.classList.contains("tg-ads-preview__avatar--inline")) {
          avatar.hidden = !showPic;
        }
      });

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
