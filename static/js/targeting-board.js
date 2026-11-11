(function () {
  function copyText(text) {
    if (!text) return Promise.reject(new Error("empty"));
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "absolute";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try {
        var ok = document.execCommand("copy");
        document.body.removeChild(ta);
        if (ok) resolve();
        else reject(new Error("copy failed"));
      } catch (err) {
        document.body.removeChild(ta);
        reject(err);
      }
    });
  }

  function flash(el, message) {
    if (!el) return;
    el.textContent = message;
    el.dataset.state = "ok";
    window.setTimeout(function () {
      el.textContent = "";
      delete el.dataset.state;
    }, 1400);
  }

  document.addEventListener("click", function (ev) {
    var allBtn = ev.target.closest("[data-targeting-copy-all-btn]");
    if (allBtn) {
      var section = allBtn.closest(".targeting-board__section");
      var src = section && section.querySelector(".targeting-board__clipboard-src");
      var text = (src && src.value) || "";
      var status = allBtn.parentElement && allBtn.parentElement.querySelector("[data-targeting-copy-status]");
      copyText(text)
        .then(function () {
          flash(status, "همه کپی شد");
        })
        .catch(function () {
          flash(status, "کپی نشد");
        });
      return;
    }
    var oneBtn = ev.target.closest("[data-targeting-copy-one]");
    if (oneBtn) {
      var item = oneBtn.getAttribute("data-targeting-copy-one") || "";
      var chipStatus = oneBtn.querySelector("[data-targeting-chip-status]");
      copyText(item)
        .then(function () {
          flash(chipStatus, "کپی شد");
          oneBtn.classList.add("targeting-card--copied");
          window.setTimeout(function () {
            oneBtn.classList.remove("targeting-card--copied");
          }, 1200);
        })
        .catch(function () {
          flash(chipStatus, "خطا");
        });
    }
  });
})();
