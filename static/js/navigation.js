/** Presentation-only navigation: focus containment, active links and mobile scroll lock. */
(function () {
  "use strict";
  var mobile = window.matchMedia("(max-width: 900px)");
  var focusable = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]';

  function boot() {
    document.querySelectorAll('.sidebar-link.active').forEach(function (link) {
      link.setAttribute('aria-current', 'page');
    });
    document.querySelectorAll('.nav-links--desktop a, .public-nav-sheet__link').forEach(function (link) {
      if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
    });
    document.querySelectorAll('.field').forEach(function (field, index) {
      var input = field.querySelector('input, select, textarea');
      if (!input) return;
      var descriptions = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
      field.querySelectorAll('.field-help, .form-error').forEach(function (hint, i) {
        if (!hint.id) hint.id = 'field-description-' + index + '-' + i;
        if (descriptions.indexOf(hint.id) < 0) descriptions.push(hint.id);
      });
      if (descriptions.length) input.setAttribute('aria-describedby', descriptions.join(' '));
      if (field.querySelector('.form-error')) input.setAttribute('aria-invalid', 'true');
    });

    document.querySelectorAll('[data-disclosure-menu]').forEach(function (menu) {
      menu.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || !menu.open) return;
        event.preventDefault();
        menu.open = false;
        menu.querySelector('summary').focus();
      });
      menu.addEventListener('toggle', function () {
        if (!menu.open) return;
        document.querySelectorAll('[data-disclosure-menu][open]').forEach(function (other) {
          if (other !== menu) other.open = false;
        });
      });
    });
    document.addEventListener('click', function (event) {
      document.querySelectorAll('[data-disclosure-menu][open]').forEach(function (menu) {
        if (!menu.contains(event.target)) menu.open = false;
      });
    });
    document.querySelectorAll('[role="tablist"]').forEach(function (list) {
      list.addEventListener('keydown', function (event) {
        var current = event.target.closest('[role="tab"]');
        if (!current || event.altKey || event.ctrlKey || event.metaKey) return;
        var tabs = Array.from(list.querySelectorAll('[role="tab"]')).filter(function (tab) {
          return !tab.disabled && tab.getAttribute('aria-disabled') !== 'true';
        });
        var index = tabs.indexOf(current);
        var rtl = getComputedStyle(list).direction === 'rtl';
        if (event.key === 'Home') index = 0;
        else if (event.key === 'End') index = tabs.length - 1;
        else if (event.key === 'ArrowRight') index += rtl ? -1 : 1;
        else if (event.key === 'ArrowLeft') index += rtl ? 1 : -1;
        else return;
        event.preventDefault();
        var next = tabs[(index + tabs.length) % tabs.length];
        if (next) { next.click(); next.focus(); }
      });
    });

    document.querySelectorAll('[data-mobile-drawer]').forEach(function (drawer) {
      var trigger = document.querySelector('[aria-controls="' + drawer.id + '"]');
      var close = drawer.querySelector('.sidebar-close, .public-nav-sheet__close');
      var active = false;
      var previousFocus = null;
      var inertStates = [];
      var background = drawer.id === 'app-sidebar'
        ? document.querySelectorAll('.app-main')
        : document.querySelectorAll('.public-nav-bar, .site-main, .site-footer');

      function sync() {
        var next = mobile.matches && drawer.classList.contains('is-open');
        drawer.inert = mobile.matches && !next;
        if (drawer.id === 'app-sidebar') document.documentElement.classList.toggle('app-nav-open', next);
        if (next === active) return;
        active = next;
        if (active) {
          previousFocus = document.activeElement;
          inertStates = Array.from(background).map(function (node) { return [node, node.inert]; });
          inertStates.forEach(function (pair) { pair[0].inert = true; });
          requestAnimationFrame(function () { if (active && close) close.focus(); });
        } else {
          inertStates.forEach(function (pair) { pair[0].inert = pair[1]; });
          inertStates = [];
          if (previousFocus && previousFocus.isConnected && mobile.matches) previousFocus.focus();
        }
      }
      drawer.addEventListener('keydown', function (event) {
        if (!active || event.key !== 'Tab') return;
        var items = Array.from(drawer.querySelectorAll(focusable)).filter(function (node) { return node.getClientRects().length > 0; });
        if (!items.length) return;
        var first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
      new MutationObserver(sync).observe(drawer, { attributes: true, attributeFilter: ['class'] });
      mobile.addEventListener('change', function () {
        if (!mobile.matches && drawer.classList.contains('is-open') && close) close.click();
        sync();
      });
      sync();
      // Existing Alpine handlers remain the sole source of open/closed state.
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
