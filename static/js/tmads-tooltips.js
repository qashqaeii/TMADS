/**
 * TMADS — premium floating tooltips for `data-tip` / native `title` (app shell only).
 * Studio field tips (`[data-studio-tip]`) also support click/tap pin.
 */
(function () {
  "use strict";

  var SHOW_MS = 180;
  var HIDE_MS = 90;
  var SKIP =
    "input,textarea,select,option,.ton-amount--convertible,[data-tip-skip],.ui-tip-pop,.ton-amount__tip,.budget-hero-card__ring-host,.budget-hero-card__popover";

  var pop = null;
  var anchor = null;
  var storedTitle = "";
  var pending = null;
  var pinned = false;
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

  function isStudioTip(el) {
    return !!(el && el.hasAttribute && el.hasAttribute("data-studio-tip"));
  }

  function tipFrom(target) {
    if (!target || !target.closest) return null;
    var el = target.closest("[data-tip], [title]");
    if (!el || skipped(el)) return null;
    var dataTip = (el.getAttribute("data-tip") || "").trim();
    var title = (el.getAttribute("title") || "").trim();
    var text = dataTip || title;
    if (!text) return null;
    return { el: el, text: text, rich: !!dataTip || isStudioTip(el), restoreTitle: title, studio: isStudioTip(el) };
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

  function setExpanded(el, on) {
    if (!el || !isStudioTip(el)) return;
    el.setAttribute("aria-expanded", on ? "true" : "false");
  }

  function position() {
    if (!pop || pop.hidden || !anchor) return;
    var rect = anchor.getBoundingClientRect();
    var gap = 10;
    pop.style.visibility = "hidden";
    pop.hidden = false;
    var width = pop.offsetWidth || 0;
    var height = pop.offsetHeight || 0;
    var top = rect.top - height - gap;
    var below = false;
    if (top < 8) {
      top = rect.bottom + gap;
      below = true;
    }
    pop.classList.toggle("ui-tip-pop--below", below);
    var rtl = document.documentElement.getAttribute("dir") === "rtl";
    var left = rtl ? rect.right - width : rect.left;
    if (isStudioTip(anchor)) {
      left = rect.left + rect.width / 2 - width / 2;
    }
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
    pinned = false;
    if (anchor && storedTitle) {
      anchor.setAttribute("title", storedTitle);
    }
    if (anchor) setExpanded(anchor, false);
    anchor = null;
    storedTitle = "";
    if (!pop) return;
    pop.classList.remove("ui-tip-pop--visible", "ui-tip-pop--rich", "ui-tip-pop--studio");
    pop.hidden = true;
    pop.textContent = "";
  }

  function show(hit, opts) {
    opts = opts || {};
    hide();
    pinned = !!opts.pin;
    anchor = hit.el;
    storedTitle = hit.restoreTitle || "";
    if (storedTitle) hit.el.removeAttribute("title");
    setExpanded(hit.el, true);
    var node = ensurePop();
    node.textContent = hit.text;
    node.classList.toggle("ui-tip-pop--rich", !!hit.rich);
    node.classList.toggle("ui-tip-pop--studio", !!hit.studio);
    node.hidden = false;
    requestAnimationFrame(function () {
      position();
      node.classList.add("ui-tip-pop--visible");
    });
  }

  function scheduleShow(hit) {
    if (pinned && anchor === hit.el) return;
    if (anchor === hit.el && pop && !pop.hidden) return;
    if (pending === hit.el) return;
    clearTimeout(hideTimer);
    clearTimeout(showTimer);
    pending = hit.el;
    showTimer = setTimeout(function () {
      pending = null;
      show(hit);
    }, SHOW_MS);
  }

  function onPointerOver(e) {
    if (!isApp() || pinned) return;
    var hit = tipFrom(e.target);
    if (!hit) return;
    scheduleShow(hit);
  }

  function onPointerOut(e) {
    if (pinned) return;
    if (!anchor && !pending) return;
    var active = anchor || pending;
    if (!active) return;
    var to = e.relatedTarget;
    if (to && (active === to || active.contains(to))) return;
    clearTimeout(showTimer);
    pending = null;
    hideTimer = setTimeout(hide, HIDE_MS);
  }

  function onFocusIn(e) {
    if (!isApp()) return;
    var hit = tipFrom(e.target);
    if (!hit || !hit.studio) return;
    scheduleShow(hit);
  }

  function onFocusOut(e) {
    if (pinned) return;
    if (!anchor && !pending) return;
    var active = anchor || pending;
    if (!active || !isStudioTip(active)) return;
    var to = e.relatedTarget;
    if (to && (active === to || active.contains(to))) return;
    clearTimeout(showTimer);
    pending = null;
    hideTimer = setTimeout(hide, HIDE_MS);
  }

  function onClick(e) {
    if (!isApp()) return;
    var hit = tipFrom(e.target);
    if (hit && hit.studio) {
      e.preventDefault();
      e.stopPropagation();
      if (pinned && anchor === hit.el) {
        hide();
        return;
      }
      show(hit, { pin: true });
      return;
    }
    if (pinned && (!hit || hit.el !== anchor)) {
      hide();
    }
  }

  function onKey(e) {
    if (e.key === "Escape" && (anchor || pending || pinned)) hide();
  }

  function onLayout() {
    if (anchor && pop && !pop.hidden) position();
  }

  function init() {
    if (!isApp()) return;
    document.addEventListener("mouseover", onPointerOver, true);
    document.addEventListener("mouseout", onPointerOut, true);
    document.addEventListener("focusin", onFocusIn, true);
    document.addEventListener("focusout", onFocusOut, true);
    document.addEventListener("click", onClick, true);
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("scroll", onLayout, true);
    window.addEventListener("resize", onLayout);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
