/* Local Telegram Ads-style preview; destination photo via authenticated Promote API only. */
(function () {
  "use strict";

  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  var AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

  function toAsciiDigits(value) {
    return String(value || "").replace(/[۰-۹٠-٩]/g, function (ch) {
      var fa = FA_DIGITS.indexOf(ch);
      if (fa >= 0) return String(fa);
      var ar = AR_DIGITS.indexOf(ch);
      return ar >= 0 ? String(ar) : ch;
    });
  }

  function formatIntAmount(amount) {
    if (!Number.isSafeInteger(amount) || amount < 0) return "";
    return amount.toLocaleString("fa-IR");
  }

  function formatDecimalAmount(amount) {
    if (!Number.isFinite(amount) || amount < 0) return "";
    return amount.toLocaleString("fa-IR", {
      useGrouping: true,
      maximumFractionDigits: 2,
      minimumFractionDigits: amount % 1 === 0 ? 0 : 2
    });
  }

  function parseIntAmount(raw) {
    var digits = toAsciiDigits(raw).replace(/[^\d]/g, "");
    if (!digits) return NaN;
    var amount = Number(digits);
    return Number.isSafeInteger(amount) ? amount : NaN;
  }

  function parseDecimalAmount(raw) {
    var text = toAsciiDigits(raw).trim().replace(/[٬,]/g, "").replace(/٫/g, ".");
    if (!text) return NaN;
    if (!/^\d+(?:\.\d{0,2})?$/.test(text) && !/^\d*\.\d{1,2}$/.test(text)) {
      var cleaned = text.replace(/[^\d.]/g, "");
      var parts = cleaned.split(".");
      if (!parts[0] && parts.length === 1) return NaN;
      text = parts.length > 1 ? parts[0] + "." + parts.slice(1).join("").slice(0, 2) : parts[0];
    }
    var amount = Number(text);
    return Number.isFinite(amount) ? amount : NaN;
  }

  function bindMoneyInputs(form) {
    form.querySelectorAll("[data-money-input]").forEach(function (input) {
      var wrap = input.closest(".studio-finance__control") || input.parentElement;
      var raw = wrap ? wrap.querySelector("[data-money-raw]") : null;
      if (!raw) return;
      var kind = input.getAttribute("data-money-kind") || "int";
      var decimal = kind === "decimal";
      var scale = Number(input.getAttribute("data-money-scale") || "1");
      if (!Number.isFinite(scale) || scale <= 0) scale = 1;
      var equivId = input.getAttribute("data-money-equiv-target") || "";
      var equiv = equivId ? document.getElementById(equivId) : null;

      function updateEquiv(units) {
        if (!equiv) return;
        if (!Number.isSafeInteger(units) || units <= 0) {
          equiv.textContent = "";
          equiv.hidden = true;
          return;
        }
        var toman = units * scale;
        if (!Number.isSafeInteger(toman)) {
          equiv.textContent = "";
          equiv.hidden = true;
          return;
        }
        equiv.hidden = false;
        equiv.textContent = "معادل " + formatIntAmount(toman) + " تومان";
      }

      function syncFromRaw() {
        var source = raw.value;
        if (!source) {
          input.value = "";
          updateEquiv(NaN);
          return;
        }
        if (decimal) {
          var d = parseDecimalAmount(source);
          input.value = Number.isFinite(d) ? formatDecimalAmount(d) : "";
          updateEquiv(NaN);
        } else {
          var n = parseIntAmount(source);
          input.value = Number.isSafeInteger(n) ? formatIntAmount(n) : "";
          updateEquiv(n);
        }
      }

      function emitRaw() {
        raw.dispatchEvent(new Event("input", { bubbles: true }));
        raw.dispatchEvent(new Event("change", { bubbles: true }));
      }

      function syncFromDisplay() {
        if (decimal) {
          var typed = toAsciiDigits(input.value);
          var endsWithSep = /[.,٫]$/.test(typed.trim());
          var amount = parseDecimalAmount(input.value);
          if (!Number.isFinite(amount)) {
            if (!toAsciiDigits(input.value).replace(/[^\d]/g, "")) {
              input.value = "";
              if (raw.value !== "") {
                raw.value = "";
                emitRaw();
              }
            }
            return;
          }
          var nextRaw = String(Math.round(amount * 100) / 100);
          var formatted = formatDecimalAmount(amount);
          if (endsWithSep && amount % 1 === 0) formatted += "٫";
          if (input.value !== formatted) {
            input.value = formatted;
            try {
              input.setSelectionRange(formatted.length, formatted.length);
            } catch (_) {}
          }
          if (raw.value !== nextRaw) {
            raw.value = nextRaw;
            emitRaw();
          }
          return;
        }
        var intAmount = parseIntAmount(input.value);
        if (!Number.isSafeInteger(intAmount)) {
          if (!toAsciiDigits(input.value).replace(/[^\d]/g, "")) {
            input.value = "";
            updateEquiv(NaN);
            if (raw.value !== "") {
              raw.value = "";
              emitRaw();
            }
          }
          return;
        }
        var nextInt = String(intAmount);
        var next = formatIntAmount(intAmount);
        if (input.value !== next) {
          input.value = next;
          try {
            input.setSelectionRange(next.length, next.length);
          } catch (_) {}
        }
        updateEquiv(intAmount);
        if (raw.value !== nextInt) {
          raw.value = nextInt;
          emitRaw();
        }
      }

      input.addEventListener("input", syncFromDisplay);
      input.addEventListener("blur", function () {
        if (decimal) {
          var amount = parseDecimalAmount(input.value);
          if (Number.isFinite(amount)) {
            raw.value = String(Math.round(amount * 100) / 100);
            input.value = formatDecimalAmount(amount);
          }
        } else {
          syncFromDisplay();
        }
      });
      syncFromRaw();
    });
  }

  function boot() {
    var panel = document.getElementById("studio-preview-panel");
    var form = document.getElementById("campaign-studio-form");
    if (!panel || !form) return;
    bindMoneyInputs(form);
    var promotePreviewUrl = form.getAttribute("data-promote-preview") || "";
    var lastPhotoKey = "";
    var photoInflight = null;
    var photoCache = {};
    var targetLabels = {
      search: "نتایج جستجو",
      bots: "ربات‌های منتخب",
      users: "برای کاربران خاص",
      channels: "داخل کانال‌ها"
    };
    var placementLabels = {
      search_result: "نتایج جستجو",
      channel_post: "پایین کانال · پیام اسپانسری",
      video_banner: "بنر روی ویدیو",
      bot_banner: "بنر در ربات"
    };
    var channelContextLabels = {
      users: "کانال مرتبط با مخاطب",
      channels: "کانال هدف",
      bots: "ربات میزبان",
      search: "نتایج جستجو"
    };
    var websiteButtonLabels = {
      "": "باز کردن وب‌سایت",
      subscribe: "اشتراک",
      view: "مشاهده",
      read: "مطالعه",
      learn_more: "اطلاعات بیشتر",
      download: "دانلود",
      open: "باز کردن",
      sign_up: "ثبت‌نام",
      buy: "خرید",
      order: "سفارش",
      play: "بازی",
      try: "امتحان کردن",
      leave_request: "ثبت درخواست"
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
      if (!el) return fallback;
      if (el.type === "radio") {
        var checkedRadio = form.querySelector('[name="' + name + '"]:checked');
        if (!checkedRadio) return fallback;
        var radioVal = checkedRadio.value;
        if (radioVal != null && String(radioVal).trim() !== "") return radioVal;
        return fallback != null && fallback !== "" ? fallback : radioVal;
      }
      var raw = el.value;
      if (raw != null && String(raw).trim() !== "") return raw;
      return fallback != null && fallback !== "" ? fallback : raw;
    }

    function checked(name) {
      var el = form.querySelector('[name="' + name + '"]');
      if (!el) return panel.dataset.previewShowUserpic === "1";
      return !!el.checked;
    }

    function resolvePlacement(kind) {
      // جایگذاری باید با نوع هدف هم‌خوان باشد؛ مقدار hidden مربوط به هدف قبلی را نادیده بگیر.
      if (kind === "search") return "search_result";
      if (kind === "bots") return "bot_banner";
      if (kind === "channels") return "channel_post";
      if (kind === "users") {
        var checkedPlacement = form.querySelector('input[type="radio"][name="placement"]:checked');
        if (checkedPlacement && checkedPlacement.value) return checkedPlacement.value;
        var dataPlacement = panel.dataset.previewPlacement || "";
        if (
          dataPlacement === "channel_post" ||
          dataPlacement === "video_banner" ||
          dataPlacement === "bot_banner"
        ) {
          return dataPlacement;
        }
        return "channel_post";
      }
      var checkedAny = form.querySelector('input[type="radio"][name="placement"]:checked');
      if (checkedAny && checkedAny.value) return checkedAny.value;
      return "channel_post";
    }

    function resolveCta(destination) {
      var custom = String(value("cta_label", panel.dataset.previewCta) || "").trim();
      if (custom) return custom;
      var dest = String(destination || "");
      var isExternal = /^https?:\/\//i.test(dest) && !/(?:t\.me|telegram\.me)\//i.test(dest);
      if (isExternal) {
        var button = String(value("button", panel.dataset.previewButton) || "");
        if (Object.prototype.hasOwnProperty.call(websiteButtonLabels, button)) {
          return websiteButtonLabels[button];
        }
      }
      // CTA در پیشنمایش تلگرام برای ربات به صورت VIEW BOT است.
      if (/(?:t\.me|telegram\.me)\/[A-Za-z0-9_]+bot\b/i.test(dest)) return "VIEW BOT";
      if (/(?:t\.me|telegram\.me)\//i.test(dest)) return "VIEW";
      return "VIEW";
    }

    function fill(selector, text) {
      panel.querySelectorAll(selector).forEach(function (el) {
        el.textContent = text;
      });
    }

    function brandFromDestination(destination, fallback) {
      var raw = String(destination || "").trim();
      if (!raw || raw === "هنوز مشخص نشده") return fallback || "";
      var match = raw.match(/(?:t\.me|telegram\.me)\/([A-Za-z0-9_]{3,64})/i);
      if (match) {
        var username = match[1];
        if (/bot$/i.test(username) && username.length > 3) {
          return username.replace(/bot$/i, "") || username;
        }
        return username;
      }
      if (raw.charAt(0) === "@") return raw.slice(1);
      return fallback || "";
    }

    function avatarNodes() {
      return panel.querySelectorAll("[data-preview-avatar].tg-ads-preview__avatar--inline");
    }

    function clearAvatarPhoto() {
      avatarNodes().forEach(function (avatar) {
        var img = avatar.querySelector("[data-preview-avatar-img]");
        var fallback = avatar.querySelector("[data-preview-avatar-fallback]");
        if (img) {
          img.removeAttribute("src");
          img.hidden = true;
        }
        if (fallback) fallback.hidden = false;
      });
    }

    function applyAvatarPhoto(url) {
      var safe = "";
      try {
        var parsed = new URL(url);
        if (parsed.protocol === "https:") safe = parsed.href;
      } catch (_) {}
      avatarNodes().forEach(function (avatar) {
        var img = avatar.querySelector("[data-preview-avatar-img]");
        var fallback = avatar.querySelector("[data-preview-avatar-fallback]");
        if (!img) return;
        if (!safe) {
          img.removeAttribute("src");
          img.hidden = true;
          if (fallback) fallback.hidden = false;
          return;
        }
        img.onload = function () {
          img.hidden = false;
          if (fallback) fallback.hidden = true;
        };
        img.onerror = function () {
          img.removeAttribute("src");
          img.hidden = true;
          if (fallback) fallback.hidden = false;
        };
        img.src = safe;
        img.hidden = false;
        if (fallback) fallback.hidden = true;
      });
    }

    function fetchPromotePhoto(destination, showPic) {
      if (!showPic) {
        lastPhotoKey = "";
        if (photoInflight && photoInflight.abort) photoInflight.abort();
        clearAvatarPhoto();
        return;
      }
      var dest = String(destination || "").trim();
      if (!dest || dest === "هنوز مشخص نشده") {
        clearAvatarPhoto();
        return;
      }
      if (photoCache[dest]) {
        applyAvatarPhoto(photoCache[dest].photo_url || "");
        if (photoCache[dest].title) {
          fill("[data-preview-brand]", photoCache[dest].title);
          fill("[data-preview-title]", photoCache[dest].title);
          fill("[data-preview-bot-host]", photoCache[dest].title);
        }
        return;
      }
      if (!promotePreviewUrl) return;
      if (lastPhotoKey === dest && photoInflight) return;
      lastPhotoKey = dest;
      if (photoInflight && photoInflight.abort) photoInflight.abort();
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      photoInflight = ctrl;
      fetch(promotePreviewUrl + "?destination=" + encodeURIComponent(dest), {
        credentials: "same-origin",
        signal: ctrl ? ctrl.signal : undefined,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          if (!j) return;
          photoCache[dest] = {
            photo_url: j.photo_url || "",
            title: j.title || ""
          };
          var currentDest = String(value("destination", panel.dataset.previewDestination) || "").trim();
          if (checked("show_userpic") && currentDest === dest) {
            applyAvatarPhoto(j.photo_url || "");
            if (j.title) {
              fill("[data-preview-brand]", j.title);
              fill("[data-preview-title]", j.title);
              fill("[data-preview-bot-host]", j.title);
            }
          }
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          clearAvatarPhoto();
        });
    }

    function activeShell(kind, placement) {
      if (kind === "search" || placement === "search_result") return "search";
      if (placement === "video_banner") return "video_banner";
      if (placement === "bot_banner" || kind === "bots") return "bot_banner";
      return "channel_post";
    }

    function update() {
      var selected = form.querySelector('[name="target_type"]:checked');
      var kind = selected ? selected.value : panel.dataset.previewType;
      var placement = resolvePlacement(kind);
      var shell = activeShell(kind, placement);
      var searchPreview = panel.querySelector("[data-preview-search]");
      var messageShells = panel.querySelectorAll("[data-preview-message]");
      if (searchPreview) searchPreview.hidden = shell !== "search";
      messageShells.forEach(function (node) {
        var id = node.getAttribute("data-preview-shell") || "channel_post";
        node.hidden = shell !== id;
      });

      var previewRoot = panel.querySelector("[data-tg-ads-preview]");
      var stage = panel.querySelector("[data-preview-stage]");
      // کاربران خاص / داخل کانال‌ها با channel_post: اسکلت بالا، تبلیغ پایین فید
      var isChannelBottom = shell === "channel_post";
      if (previewRoot) {
        previewRoot.setAttribute("data-preview-kind", kind || "");
        previewRoot.setAttribute("data-preview-shell", shell);
        previewRoot.classList.toggle("tg-ads-preview--channel-bottom", isChannelBottom);
        previewRoot.classList.toggle("tg-ads-preview--users", kind === "users");
        previewRoot.classList.toggle("tg-ads-preview--channels", kind === "channels");
        previewRoot.classList.toggle("tg-ads-preview--bots", kind === "bots");
        previewRoot.classList.toggle("tg-ads-preview--search", kind === "search");
      }
      if (stage) {
        stage.setAttribute("data-preview-shell", shell);
        stage.classList.toggle("is-channel-post", shell === "channel_post");
        stage.classList.toggle("is-channel-bottom", isChannelBottom);
        stage.classList.toggle("is-video-banner", shell === "video_banner");
        stage.classList.toggle("is-bot-banner", shell === "bot_banner");
        stage.classList.toggle("is-search", shell === "search");
      }

      var targetLabel = targetLabels[kind] || "تبلیغ در تلگرام";
      var campaignName = value("campaign_name", panel.dataset.previewName) || "بدون عنوان";
      var destination = value("destination", panel.dataset.previewDestination) || "هنوز مشخص نشده";
      var adText = value("ad_text", panel.dataset.previewText) || "متن تبلیغ شما";
      // نام داخل حباب تبلیغ از مقصد می‌آید؛ عنوان کمپین فقط برای پنل مدیریت است.
      var brand = brandFromDestination(destination, "") || "مقصد تبلیغ";
      var showPic = checked("show_userpic");
      var cta = resolveCta(destination);
      var placementLabel = placementLabels[placement] || placementLabels.channel_post;
      if (shell === "bot_banner" && kind === "bots") placementLabel = placementLabels.bot_banner;
      if (shell === "channel_post") placementLabel = placementLabels.channel_post;

      fill("[data-preview-mode]", targetLabel);
      fill("[data-preview-target-label]", targetLabel);
      fill("[data-preview-placement-label]", placementLabel);
      fill("[data-preview-channel-context]", channelContextLabels[kind] || channelContextLabels.channels);
      fill("[data-preview-title]", brand);
      fill("[data-preview-brand]", brand);
      fill("[data-preview-campaign-name]", campaignName);
      fill("[data-preview-url]", destination);
      fill("[data-preview-destination-text]", destination);
      fill("[data-preview-copy]", adText);
      fill("[data-preview-cta-label]", cta);
      if (shell === "bot_banner") {
        var botHost = brand && brand !== "مقصد تبلیغ" ? brand : "ربات میزبان";
        if (kind === "bots") botHost = brand && brand !== "مقصد تبلیغ" ? brand : "ربات هدف";
        fill("[data-preview-bot-host]", botHost);
      }

      avatarNodes().forEach(function (avatar) {
        // فقط آواتارهای داخل شِل فعال را مدیریت کن
        var shellRoot = avatar.closest("[data-preview-message], [data-preview-search]");
        if (shellRoot && shellRoot.hidden) return;
        avatar.hidden = !showPic;
      });
      form.querySelectorAll("[data-cpm-userpic-badge], [data-cpm-userpic-hint]").forEach(function (el) {
        el.hidden = !showPic;
      });
      fetchPromotePhoto(destination, showPic && shell !== "search");

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

    var updateDebounced = (function () {
      var t;
      return function () {
        clearTimeout(t);
        t = setTimeout(update, 280);
      };
    })();

    form.addEventListener("input", updateDebounced);
    form.addEventListener("change", update);
    update();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
