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
      var input = field.querySelector('input:not([type="hidden"]), select, textarea');
      if (!input) return;
      var descriptions = (input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
      field.querySelectorAll('.field-help, .form-error').forEach(function (hint, i) {
        if (!hint.id) hint.id = 'field-description-' + index + '-' + i;
        if (descriptions.indexOf(hint.id) < 0) descriptions.push(hint.id);
      });
      if (descriptions.length) input.setAttribute('aria-describedby', descriptions.join(' '));
      if (field.querySelector('.form-error')) input.setAttribute('aria-invalid', 'true');
    });

    document.querySelectorAll('.table-scroll, .table-wrap').forEach(function (region) {
      if (!region.hasAttribute('tabindex')) region.tabIndex = 0;
      if (!region.hasAttribute('role')) region.setAttribute('role','region');
      if (!region.hasAttribute('aria-label') && !region.hasAttribute('aria-labelledby')) region.setAttribute('aria-label','جدول اطلاعات؛ پیمایش افقی');
    });

    function disclosurePanel(menu) {
      return menu.querySelector('.row-actions__menu, .exec-menu__panel');
    }

    function clearDisclosurePanel(menu) {
      var panel = disclosurePanel(menu);
      if (!panel) return;
      panel.style.position = '';
      panel.style.top = '';
      panel.style.left = '';
      panel.style.right = '';
      panel.style.bottom = '';
      panel.style.width = '';
      panel.style.minWidth = '';
      panel.style.zIndex = '';
      panel.style.insetInlineEnd = '';
    }

    function placeDisclosurePanel(menu) {
      var panel = disclosurePanel(menu);
      var summary = menu.querySelector('summary');
      if (!panel || !summary) return;
      var rect = summary.getBoundingClientRect();
      var rtl = getComputedStyle(document.documentElement).direction === 'rtl'
        || getComputedStyle(menu).direction === 'rtl';
      panel.style.position = 'fixed';
      panel.style.zIndex = '5000';
      panel.style.insetInlineEnd = 'auto';
      panel.style.right = 'auto';
      panel.style.bottom = 'auto';
      panel.style.minWidth = Math.max(rect.width, 176) + 'px';
      panel.style.top = '0px';
      panel.style.left = '0px';
      var width = panel.offsetWidth || 176;
      var height = panel.offsetHeight || 0;
      var gap = 4;
      var top = rect.bottom + gap;
      if (top + height > window.innerHeight - 8 && rect.top - gap - height > 8) {
        top = rect.top - gap - height;
      }
      var left = rtl ? rect.left : rect.right - width;
      left = Math.min(Math.max(8, left), window.innerWidth - width - 8);
      panel.style.top = top + 'px';
      panel.style.left = left + 'px';
    }

    document.querySelectorAll('[data-disclosure-menu]').forEach(function (menu) {
      menu.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || !menu.open) return;
        event.preventDefault();
        menu.open = false;
        clearDisclosurePanel(menu);
        menu.querySelector('summary').focus();
      });
      menu.addEventListener('toggle', function () {
        if (!menu.open) {
          clearDisclosurePanel(menu);
          return;
        }
        document.querySelectorAll('[data-disclosure-menu][open]').forEach(function (other) {
          if (other !== menu) other.open = false;
        });
        placeDisclosurePanel(menu);
        requestAnimationFrame(function () {
          if (menu.open) placeDisclosurePanel(menu);
        });
      });
    });
    document.addEventListener('click', function (event) {
      document.querySelectorAll('[data-disclosure-menu][open]').forEach(function (menu) {
        if (!menu.contains(event.target)) menu.open = false;
      });
    });
    window.addEventListener('resize', function () {
      document.querySelectorAll('[data-disclosure-menu][open]').forEach(placeDisclosurePanel);
    });
    document.addEventListener('scroll', function () {
      document.querySelectorAll('[data-disclosure-menu][open]').forEach(function (menu) {
        menu.open = false;
      });
    }, true);
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
