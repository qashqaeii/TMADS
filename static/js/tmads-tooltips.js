/**
 * TMADS — premium floating tooltips for native `title` (app shell only).
 */
(function () {
  "use strict";

  var SHOW_MS = 280;
  var HIDE_MS = 50;
  var SKIP =
    "input,textarea,select,option,.ton-amount--convertible,[data-tip-skip],.ui-tip-pop,.ton-amount__tip,.budget-hero-card__ring-host,.budget-hero-card__popover";

  var pop = null;
  var anchor = null;
  var storedTitle = "";
  var pending = null;
  var showTimer = null;
  var hideTimer = null;

  function isApp() {
    return document.body && document.body.classList.contains("is-app");
  }

  function skipped(node) {
    if (!node || !node.closest) return true;
    try {
      if (node.matches(SKIP) || node.closest(SKIP)) return true;
      if (node.closest("canvas")) return true;
    } catch (e) {
      return true;
    }
    return false;
  }

  function titledFrom(target) {
    if (!target || !target.closest) return null;
    var el = target.closest("[title]");
    if (!el || skipped(el)) return null;
    var text = (el.getAttribute("title") || "").trim();
    if (!text) return null;
    return { el: el, text: text };
  }

  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.className = "ui-tip-pop ui-tip-surface";
    pop.setAttribute("role", "tooltip");
    pop.hidden = true;
    document.body.appendChild(pop);
    return pop;
  }

  function position() {
    if (!pop || pop.hidden || !anchor) return;
    var rect = anchor.getBoundingClientRect();
    var gap = 9;
    pop.style.visibility = "hidden";
    pop.hidden = false;
    var width = pop.offsetWidth;
    var height = pop.offsetHeight;
    var top = rect.top - height - gap;
    var below = false;
    if (top < 8) {
      top = rect.bottom + gap;
      below = true;
    }
    pop.classList.toggle("ui-tip-pop--below", below);
    var rtl = document.documentElement.getAttribute("dir") === "rtl";
    var left = rtl ? rect.right - width : rect.left;
    var pad = 10;
    if (left < pad) left = pad;
    if (left + width > window.innerWidth - pad) {
      left = window.innerWidth - width - pad;
    }
    pop.style.top = Math.round(top) + "px";
    pop.style.left = Math.round(left) + "px";
    pop.style.visibility = "";
  }

  function hide() {
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    pending = null;
    if (anchor && storedTitle) {
      anchor.setAttribute("title", storedTitle);
    }
    anchor = null;
    storedTitle = "";
    if (!pop) return;
    pop.classList.remove("ui-tip-pop--visible");
    pop.hidden = true;
    pop.textContent = "";
  }

  function show(el, text) {
    hide();
    anchor = el;
    storedTitle = text;
    el.removeAttribute("title");
    var node = ensurePop();
    node.textContent = text;
    node.hidden = false;
    requestAnimationFrame(function () {
      position();
      node.classList.add("ui-tip-pop--visible");
    });
  }

  function scheduleShow(hit) {
    if (anchor === hit.el && pop && !pop.hidden) return;
    if (pending === hit.el) return;
    clearTimeout(hideTimer);
    clearTimeout(showTimer);
    pending = hit.el;
    showTimer = setTimeout(function () {
      pending = null;
      show(hit.el, hit.text);
    }, SHOW_MS);
  }

  function onPointerOver(e) {
    if (!isApp()) return;
    var hit = titledFrom(e.target);
    if (!hit) return;
    scheduleShow(hit);
  }

  function onPointerOut(e) {
    if (!anchor && !pending) return;
    var active = anchor || pending;
    if (!active) return;
    var to = e.relatedTarget;
    if (to && (active === to || active.contains(to))) return;
    clearTimeout(showTimer);
    pending = null;
    hideTimer = setTimeout(hide, HIDE_MS);
  }

  function onLayout() {
    if (anchor && pop && !pop.hidden) position();
  }

  function init() {
    if (!isApp()) return;
    document.addEventListener("mouseover", onPointerOver, true);
    document.addEventListener("mouseout", onPointerOut, true);
    document.addEventListener("scroll", onLayout, true);
    window.addEventListener("resize", onLayout);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
