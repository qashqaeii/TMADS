/**
 * Budget ring hero — fixed-layer tooltip (viewport-safe, above page chrome).
 */
(function () {
  "use strict";

  var pad = 12;
  var gap = 10;
  var active = null;

  function anchorFor(tip) {
    return tip.__budgetRingHost || null;
  }

  function position(host, tip) {
    var rect = host.getBoundingClientRect();
    tip.style.display = "block";
    var tw = tip.offsetWidth;
    var th = tip.offsetHeight;
    var top = rect.bottom + gap;
    var above = top + th > window.innerHeight - pad;
    if (above) {
      top = Math.max(pad, rect.top - th - gap);
      tip.classList.add("budget-hero-tip--above");
    } else {
      tip.classList.remove("budget-hero-tip--above");
    }
    var left = rect.left + rect.width / 2 - tw / 2;
    if (left < pad) left = pad;
    if (left + tw > window.innerWidth - pad) {
      left = window.innerWidth - tw - pad;
    }
    tip.style.top = Math.round(top) + "px";
    tip.style.left = Math.round(left) + "px";
    var tipRect = tip.getBoundingClientRect();
    var arrowX = rect.left + rect.width / 2 - tipRect.left;
    arrowX = Math.max(18, Math.min(tipRect.width - 18, arrowX));
    tip.style.setProperty("--tip-arrow-x", Math.round(arrowX) + "px");
  }

  function open(host, tip) {
    if (active && active.tip === tip) {
      position(host, tip);
      return;
    }
    placeClose();

    var marker = document.createComment("budget-hero-tip-anchor");
    host.appendChild(marker);
    tip.__budgetRingHost = host;
    tip.__budgetRingMarker = marker;
    document.body.appendChild(tip);
    tip.classList.add("is-open");
    active = { host: host, tip: tip, marker: marker };
    position(host, tip);
  }

  function placeClose() {
    if (!active) return;
    var tip = active.tip;
    var marker = active.marker;
    tip.classList.remove("is-open", "budget-hero-tip--above");
    tip.style.top = "";
    tip.style.left = "";
    tip.style.display = "";
    if (marker && marker.parentNode) {
      marker.parentNode.insertBefore(tip, marker);
      marker.remove();
    }
    delete tip.__budgetRingHost;
    delete tip.__budgetRingMarker;
    active = null;
  }

  function shouldKeepOpen(host, tip) {
    return host.matches(":hover") || tip.matches(":hover") || host.contains(document.activeElement);
  }

  function scheduleClose(host, tip) {
    window.setTimeout(function () {
      if (shouldKeepOpen(host, tip)) return;
      placeClose();
    }, 50);
  }

  function bind(host) {
    var tip = host.querySelector(".budget-hero-card__popover");
    if (!tip) return;

    host.addEventListener("mouseenter", function () {
      open(host, tip);
    });
    host.addEventListener("focusin", function () {
      open(host, tip);
    });
    host.addEventListener("mouseleave", function () {
      scheduleClose(host, tip);
    });
    host.addEventListener("focusout", function () {
      scheduleClose(host, tip);
    });
    tip.addEventListener("mouseenter", function () {
      open(host, tip);
    });
    tip.addEventListener("mouseleave", function () {
      scheduleClose(host, tip);
    });
  }

  function onLayout() {
    if (!active) return;
    position(active.host, active.tip);
  }

  function init() {
    document.querySelectorAll(".budget-hero-card__ring-host").forEach(bind);
    window.addEventListener("resize", onLayout);
    document.addEventListener("scroll", onLayout, true);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") placeClose();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
