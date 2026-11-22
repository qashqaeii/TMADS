/**
 * Jalali datetime picker — Telegram Ads-inspired, RTL / Persian digits.
 */
(function () {
  "use strict";

  var MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
  ];
  var WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  var activeHost = null;
  var shell = null;
  var state = { viewJy: 1404, viewJm: 1, selected: null };

  function toFa(n) {
    return String(n).replace(/\d/g, function (d) { return FA[+d]; });
  }

  function toEn(s) {
    return String(s || "")
      .replace(/[۰-۹]/g, function (d) { return String(FA.indexOf(d)); })
      .replace(/[٠-٩]/g, function (d) { return String("٠١٢٣٤٥٦٧٨٩".indexOf(d)); });
  }

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function g2j(gy, gm, gd) {
    var gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var gy2 = gm > 2 ? gy + 1 : gy;
    var days = 355666 + 365 * gy + ~~((gy2 + 3) / 4) - ~~((gy2 + 99) / 100)
      + ~~((gy2 + 399) / 400) + gd + gdm[gm - 1];
    var jy = -1595 + 33 * ~~(days / 12053);
    days %= 12053;
    jy += 4 * ~~(days / 1461);
    days %= 1461;
    if (days > 365) {
      jy += ~~((days - 1) / 365);
      days = (days - 1) % 365;
    }
    var jm = days < 186 ? 1 + ~~(days / 31) : 7 + ~~((days - 186) / 30);
    var jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return { jy: jy, jm: jm, jd: jd };
  }

  function j2g(jy, jm, jd) {
    jy += 1595;
    var days = -355668 + 365 * jy + ~~(jy / 33) * 8 + ~~(((jy % 33) + 3) / 4)
      + jd + (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
    var gy = 400 * ~~(days / 146097);
    days %= 146097;
    if (days > 36524) {
      gy += 100 * ~~(--days / 36524);
      days %= 36524;
      if (days >= 365) days++;
    }
    gy += 4 * ~~(days / 1461);
    days %= 1461;
    if (days > 365) {
      gy += ~~((days - 1) / 365);
      days = (days - 1) % 365;
    }
    var gd = days + 1;
    var sal = [0, 31, (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0 ? 29 : 28,
      31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var gm = 0;
    for (; gm < 13 && gd > sal[gm]; gm++) gd -= sal[gm];
    return { gy: gy, gm: gm, gd: gd };
  }

  function isLeap(jy) {
    var a = j2g(jy, 1, 1);
    var b = j2g(jy + 1, 1, 1);
    var ms = Date.UTC(b.gy, b.gm - 1, b.gd) - Date.UTC(a.gy, a.gm - 1, a.gd);
    return ms / 86400000 === 366;
  }

  function monthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return isLeap(jy) ? 30 : 29;
  }

  function formatValue(jy, jm, jd, hour, minute) {
    return toFa(jy + "/" + pad2(jm) + "/" + pad2(jd) + " " + pad2(hour) + ":" + pad2(minute));
  }

  function parseValue(raw) {
    var m = toEn(raw).trim().match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$/);
    if (!m) return null;
    var jy = +m[1], jm = +m[2], jd = +m[3];
    var hour = m[4] != null ? +m[4] : 12;
    var minute = m[5] != null ? +m[5] : 0;
    if (jm < 1 || jm > 12 || jd < 1 || jd > monthLength(jy, jm)) return null;
    if (hour > 23 || minute > 59) return null;
    return { jy: jy, jm: jm, jd: jd, hour: hour, minute: minute };
  }

  function todayJalali() {
    var now = new Date();
    var j = g2j(now.getFullYear(), now.getMonth() + 1, now.getDate());
    return { jy: j.jy, jm: j.jm, jd: j.jd, hour: now.getHours(), minute: now.getMinutes() };
  }

  function weekdaySat0(jy, jm, jd) {
    var g = j2g(jy, jm, jd);
    return (new Date(g.gy, g.gm - 1, g.gd).getDay() + 1) % 7;
  }

  function applyToInput() {
    if (!activeHost || !state.selected) return;
    var input = activeHost.querySelector("[data-jalali-input]");
    if (!input) return;
    var s = state.selected;
    input.value = formatValue(s.jy, s.jm, s.jd, s.hour, s.minute);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function syncTimeFromInputs() {
    if (!activeHost || !state.selected) return;
    var hourEl = shell.querySelector("[data-jdp-hour]");
    var minuteEl = shell.querySelector("[data-jdp-minute]");
    var hour = Math.min(23, Math.max(0, parseInt(toEn(hourEl.value), 10) || 0));
    var minute = Math.min(59, Math.max(0, parseInt(toEn(minuteEl.value), 10) || 0));
    state.selected.hour = hour;
    state.selected.minute = minute;
    hourEl.value = toFa(pad2(hour));
    minuteEl.value = toFa(pad2(minute));
    applyToInput();
  }

  function render() {
    ensureShell();
    shell.querySelector("[data-jdp-title]").textContent =
      MONTHS[state.viewJm - 1] + " " + toFa(state.viewJy);

    var hourEl = shell.querySelector("[data-jdp-hour]");
    var minuteEl = shell.querySelector("[data-jdp-minute]");
    if (state.selected) {
      hourEl.value = toFa(pad2(state.selected.hour));
      minuteEl.value = toFa(pad2(state.selected.minute));
    } else {
      hourEl.value = toFa("12");
      minuteEl.value = toFa("00");
    }

    var grid = shell.querySelector("[data-jdp-grid]");
    grid.innerHTML = "";

    var firstDow = weekdaySat0(state.viewJy, state.viewJm, 1);
    var daysInMonth = monthLength(state.viewJy, state.viewJm);
    var prevJm = state.viewJm === 1 ? 12 : state.viewJm - 1;
    var prevJy = state.viewJm === 1 ? state.viewJy - 1 : state.viewJy;
    var prevLen = monthLength(prevJy, prevJm);
    var today = todayJalali();
    var cells = [];
    var i;

    for (i = 0; i < firstDow; i++) {
      cells.push({ jy: prevJy, jm: prevJm, jd: prevLen - firstDow + i + 1, outside: true });
    }
    for (i = 1; i <= daysInMonth; i++) {
      cells.push({ jy: state.viewJy, jm: state.viewJm, jd: i, outside: false });
    }
    var nextJd = 1;
    var nextJm = state.viewJm === 12 ? 1 : state.viewJm + 1;
    var nextJy = state.viewJm === 12 ? state.viewJy + 1 : state.viewJy;
    while (cells.length < 42) {
      cells.push({ jy: nextJy, jm: nextJm, jd: nextJd++, outside: true });
    }

    cells.forEach(function (cell) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "studio-jdp__day";
      btn.textContent = toFa(cell.jd);
      btn.setAttribute("role", "gridcell");
      if (cell.outside) btn.classList.add("is-outside");
      if (
        state.selected &&
        state.selected.jy === cell.jy &&
        state.selected.jm === cell.jm &&
        state.selected.jd === cell.jd
      ) {
        btn.classList.add("is-selected");
        btn.setAttribute("aria-selected", "true");
      }
      if (today.jy === cell.jy && today.jm === cell.jm && today.jd === cell.jd) {
        btn.classList.add("is-today");
      }
      btn.addEventListener("click", function () {
        var hour = state.selected ? state.selected.hour : 12;
        var minute = state.selected ? state.selected.minute : 0;
        state.selected = {
          jy: cell.jy, jm: cell.jm, jd: cell.jd, hour: hour, minute: minute,
        };
        if (cell.outside) {
          state.viewJy = cell.jy;
          state.viewJm = cell.jm;
        }
        applyToInput();
        render();
      });
      grid.appendChild(btn);
    });
  }

  function ensureShell() {
    if (shell && shell.dataset.jdpVersion === "2") return shell;
    if (shell && shell.parentNode) shell.parentNode.removeChild(shell);
    shell = document.createElement("div");
    shell.className = "studio-jdp";
    shell.dataset.jdpVersion = "2";
    shell.hidden = true;
    shell.innerHTML =
      '<div class="studio-jdp__backdrop" data-jdp-close></div>' +
      '<div class="studio-jdp__dialog" role="dialog" aria-modal="true" aria-label="انتخاب تاریخ شمسی">' +
      '<div class="studio-jdp__card">' +
      '<header class="studio-jdp__head">' +
      '<strong class="studio-jdp__title" data-jdp-title></strong>' +
      '<div class="studio-jdp__nav">' +
      '<button type="button" class="studio-jdp__nav-btn" data-jdp-prev aria-label="ماه قبل">' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 15l6-6 6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      "</button>" +
      '<button type="button" class="studio-jdp__nav-btn" data-jdp-next aria-label="ماه بعد">' +
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      "</button>" +
      "</div></header>" +
      '<div class="studio-jdp__weekdays" aria-hidden="true"></div>' +
      '<div class="studio-jdp__grid" data-jdp-grid role="grid"></div>' +
      '<div class="studio-jdp__time">' +
      '<input type="text" class="studio-jdp__time-input" inputmode="numeric" maxlength="2" data-jdp-hour aria-label="ساعت" placeholder="۱۲">' +
      '<span class="studio-jdp__time-sep" aria-hidden="true">:</span>' +
      '<input type="text" class="studio-jdp__time-input" inputmode="numeric" maxlength="2" data-jdp-minute aria-label="دقیقه" placeholder="۰۰">' +
      '<span class="studio-jdp__tz">ایران ‎+۳:۳۰</span>' +
      "</div>" +
      '<footer class="studio-jdp__foot">' +
      '<button type="button" class="studio-jdp__link" data-jdp-clear>پاک کردن</button>' +
      '<button type="button" class="studio-jdp__link studio-jdp__link--strong" data-jdp-done>بستن</button>' +
      "</footer></div></div>";

    var week = shell.querySelector(".studio-jdp__weekdays");
    WEEKDAYS.forEach(function (w) {
      var s = document.createElement("span");
      s.textContent = w;
      week.appendChild(s);
    });

    shell.querySelector("[data-jdp-close]").addEventListener("click", close);
    shell.querySelector("[data-jdp-done]").addEventListener("click", close);
    shell.querySelector("[data-jdp-clear]").addEventListener("click", function () {
      if (!activeHost) return;
      var input = activeHost.querySelector("[data-jalali-input]");
      if (input) {
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
      state.selected = null;
      close();
    });
    shell.querySelector("[data-jdp-prev]").addEventListener("click", function () {
      state.viewJm -= 1;
      if (state.viewJm < 1) { state.viewJm = 12; state.viewJy -= 1; }
      render();
    });
    shell.querySelector("[data-jdp-next]").addEventListener("click", function () {
      state.viewJm += 1;
      if (state.viewJm > 12) { state.viewJm = 1; state.viewJy += 1; }
      render();
    });
    shell.querySelector("[data-jdp-hour]").addEventListener("change", syncTimeFromInputs);
    shell.querySelector("[data-jdp-minute]").addEventListener("change", syncTimeFromInputs);
    shell.querySelector("[data-jdp-hour]").addEventListener("blur", syncTimeFromInputs);
    shell.querySelector("[data-jdp-minute]").addEventListener("blur", syncTimeFromInputs);

    document.addEventListener("keydown", function (e) {
      if (!shell || shell.hidden) return;
      if (e.key === "Escape") { e.preventDefault(); close(); }
    });

    document.body.appendChild(shell);
    return shell;
  }

  function open(host) {
    ensureShell();
    activeHost = host;
    var input = host.querySelector("[data-jalali-input]");
    var parsed = parseValue(input && input.value);
    var base = parsed || todayJalali();
    state.selected = parsed
      ? { jy: parsed.jy, jm: parsed.jm, jd: parsed.jd, hour: parsed.hour, minute: parsed.minute }
      : null;
    state.viewJy = base.jy;
    state.viewJm = base.jm;
    render();
    shell.hidden = false;
    document.documentElement.classList.add("studio-jdp-open");
    var done = shell.querySelector("[data-jdp-done]");
    if (done) done.focus();
  }

  function close() {
    if (!shell) return;
    shell.hidden = true;
    document.documentElement.classList.remove("studio-jdp-open");
    var host = activeHost;
    activeHost = null;
    if (host) {
      var input = host.querySelector("[data-jalali-input]");
      if (input) input.focus();
    }
  }

  function initHost(host) {
    if (!host || host.dataset.jalaliReady === "1") return;
    host.dataset.jalaliReady = "1";
    var input = host.querySelector("[data-jalali-input]");
    var openBtn = host.querySelector("[data-jalali-open]");
    function openPicker(e) {
      if (e) e.preventDefault();
      open(host);
    }
    if (openBtn) openBtn.addEventListener("click", openPicker);
    if (input) {
      input.setAttribute("readonly", "readonly");
      input.addEventListener("click", openPicker);
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
          e.preventDefault();
          openPicker();
        }
      });
    }
  }

  function init(root) {
    (root || document).querySelectorAll("[data-jalali-datetime]").forEach(initHost);
  }

  window.StudioJalaliPicker = { init: init, open: open, close: close };
  document.addEventListener("DOMContentLoaded", function () { init(document); });
})();
