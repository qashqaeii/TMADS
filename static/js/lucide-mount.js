/**
 * Mount Lucide icons (data-lucide) — official SVG set.
 */
(function () {
  function markReady(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[data-lucide-host]").forEach(function (shell) {
      if (shell.querySelector("svg.lucide, svg.df-lucide-svg")) {
        shell.classList.add("icon-shell--ready");
      }
    });
  }

  function mountLucide(root) {
    if (!window.lucide || typeof window.lucide.createIcons !== "function") {
      return;
    }
    var opts = {
      attrs: {
        class: "lucide-svg df-lucide-svg",
        "stroke-width": "1.75",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        "aria-hidden": "true",
        role: "img",
      },
      nameAttr: "data-lucide",
    };
    if (root && root !== document) {
      opts.root = root;
    }
    window.lucide.createIcons(opts);
    markReady(root || document);
  }

  function boot() {
    mountLucide(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  document.body.addEventListener("htmx:afterSettle", function (evt) {
    if (evt.detail && evt.detail.target) {
      mountLucide(evt.detail.target);
    }
  });

  window.tmadsMountLucide = mountLucide;
})();
