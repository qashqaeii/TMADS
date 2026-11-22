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

  function parseAmount(value) {
    var digits = toAsciiDigits(value).replace(/[^\d]/g, "");
    if (!digits) return NaN;
    var amount = Number(digits);
    return Number.isSafeInteger(amount) ? amount : NaN;
  }

  function formatAmount(amount) {
    if (!Number.isSafeInteger(amount) || amount < 0) return "";
    return amount.toLocaleString("fa-IR");
  }

  function boot() {
    var status = document.querySelector("[data-pay-copy-status]");
    if (status && navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      document.querySelectorAll("[data-pay-copy]").forEach(function (button) {
        var target = document.getElementById(button.dataset.payCopy);
        if (!target) return;
        button.hidden = false;
        button.addEventListener("click", function () {
          navigator.clipboard.writeText(target.textContent.trim()).then(function () {
            status.hidden = false;
            status.textContent = "شناسه کپی شد.";
          }).catch(function () {
            status.hidden = false;
            status.textContent = "کپی خودکار ممکن نیست؛ شناسه را انتخاب و کپی کنید.";
          });
        });
      });
    }

    var recheck = document.querySelector("[data-pay-recheck]");
    if (recheck) {
      var checkButton = recheck.querySelector("button[type=submit]");
      var checkLabel = recheck.querySelector("[data-pay-submit-label]");
      recheck.addEventListener("submit", function (event) {
        if (checkButton.disabled) {
          event.preventDefault();
          return;
        }
        checkButton.disabled = true;
        checkLabel.textContent = "در حال بررسی…";
      });
      window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
          checkButton.disabled = false;
          checkLabel.textContent = "بررسی مجدد وضعیت";
        }
      });
    }

    var form = document.querySelector("[data-topup-form]");
    if (!form) return;
    var input = form.querySelector("#topup-amount");
    var row = form.querySelector("[data-quick-amounts]");
    var total = form.querySelector("[data-topup-total]");
    if (!input || !row || !total) return;

    row.hidden = false;
    total.hidden = false;
    var quickBox = form.querySelector("[data-quick-amounts-box]");
    if (quickBox) quickBox.hidden = false;

    function setAmount(amount, syncInput) {
      if (syncInput) input.value = formatAmount(amount);
      var valueNode = total.querySelector("[data-topup-value]");
      valueNode.textContent =
        Number.isSafeInteger(amount) && amount >= 1000
          ? formatAmount(amount) + " تومان"
          : "—";
      row.querySelectorAll("[data-amount]").forEach(function (button) {
        button.setAttribute(
          "aria-pressed",
          String(Number.isSafeInteger(amount) && Number(button.dataset.amount) === amount)
        );
      });
    }

    function updateFromInput() {
      var amount = parseAmount(input.value);
      if (Number.isSafeInteger(amount)) {
        var formatted = formatAmount(amount);
        if (input.value !== formatted) {
          var start = input.selectionStart;
          input.value = formatted;
          if (typeof start === "number") {
            input.setSelectionRange(formatted.length, formatted.length);
          }
        }
      } else if (!toAsciiDigits(input.value).replace(/[^\d]/g, "")) {
        input.value = "";
      }
      setAmount(amount, false);
    }

    row.addEventListener("click", function (event) {
      var button = event.target.closest("[data-amount]");
      if (!button) return;
      setAmount(Number(button.dataset.amount), true);
      input.focus();
    });

    input.addEventListener("input", updateFromInput);
    updateFromInput();

    var submit = form.querySelector("[data-payment-submit]");
    if (submit) {
      form.addEventListener("submit", function (event) {
        if (submit.disabled) {
          event.preventDefault();
          return;
        }
        var amount = parseAmount(input.value);
        if (!Number.isSafeInteger(amount) || amount < 1000) {
          event.preventDefault();
          input.focus();
          return;
        }
        input.value = String(amount);
        submit.disabled = true;
        (submit.querySelector("[data-pay-submit-label]") || submit).textContent =
          "در حال آماده‌سازی پرداخت…";
      });
      window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
          submit.disabled = false;
          (submit.querySelector("[data-pay-submit-label]") || submit).textContent =
            "ادامه پرداخت";
          updateFromInput();
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
