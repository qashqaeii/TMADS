/**
 * TMADS motion — scroll reveal & stagger indices (respects reduced motion).
 */
(function () {
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function markRevealed(nodes) {
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].classList.add("is-revealed");
    }
  }

  function revealInRoot(root) {
    if (!root) return;
    markRevealed(root.querySelectorAll(".motion-reveal:not(.is-revealed)"));
  }

  window.tmadsRevealIn = revealInRoot;

  function assignStaggerIndices(root) {
    var scope = root || document;
    scope.querySelectorAll(".page-frame").forEach(function (frame) {
      var kids = frame.children;
      for (var i = 0; i < kids.length; i++) {
        kids[i].style.setProperty("--motion-section", String(i));
      }
    });
    scope.querySelectorAll(".kpi-exec-grid, .kpi-luxe, .dash-kpi-board__grid, .dash-campaign-list").forEach(function (grid) {
      var items = grid.querySelectorAll(".kpi-exec, .kpi-luxe__item, .dash-kpi-tile, .dash-campaign-list__item");
      for (var j = 0; j < items.length; j++) {
        items[j].style.setProperty("--motion-kpi", String(j));
      }
    });
  }

  var revealSelector = [
    ".card",
    ".panel-grid > *",
    ".table-card",
    ".filter-card",
    ".empty-state",
    ".timeline-item",
    ".campaign-row",
    ".wizard-form",
    ".wizard-progress--exec",
    ".step-card",
    ".feature-card",
    ".ops-links a",
    ".state-banner",
    ".hero-panel--exec",
    ".dash-kpi-board",
    ".dash-hero",
    ".campaign-kpi-board",
    ".campaigns-filter--luxe",
    ".campaigns-table-board--luxe",
    ".campaign-trend-card",
    ".campaign-analytics-trend",
    ".campaign-analytics-funnel",
    ".campaign-analytics-spend",
  ].join(",");

  function initReveal(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll(revealSelector);
    if (!nodes.length) return;

    if (reduced || !("IntersectionObserver" in window)) {
      markRevealed(nodes);
      return;
    }

    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-revealed");
            io.unobserve(entry.target);
          }
        });
      },
      { root: null, rootMargin: "0px 0px -6% 0px", threshold: 0.06 }
    );

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (!el.classList.contains("motion-reveal")) {
        el.classList.add("motion-reveal");
      }
      io.observe(el);
    }
  }

  function boot(root) {
    document.documentElement.classList.add(reduced ? "motion-reduced" : "motion-ready");
    assignStaggerIndices(root);
    initReveal(root);
  }

  function revealVisibleCampaignTabs() {
    document.querySelectorAll(".campaign-detail .tab-panel").forEach(function (panel) {
      if (panel.offsetParent !== null) {
        revealInRoot(panel);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      boot();
      revealVisibleCampaignTabs();
    });
  } else {
    boot();
    revealVisibleCampaignTabs();
  }

  document.addEventListener("alpine:initialized", revealVisibleCampaignTabs);

  document.body.addEventListener("htmx:afterSettle", function () {
    boot(document.querySelector(".page-frame") || document);
    revealVisibleCampaignTabs();
  });
})();
