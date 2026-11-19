/* Shared confirmation dialog. Backend authorization and CSRF remain unchanged. */
(function () {
  "use strict";
  var dialog = document.getElementById("ui-confirmation");
  var pending = null;
  var bypass = null;
  function boot() {
    document.querySelectorAll("[data-dismiss-notice]").forEach(function (button) {
      button.hidden = false;
      button.addEventListener("click", function () {
        var notice = button.closest(".ui-notice");
        if (notice) notice.remove();
      });
    });
    if (!dialog || typeof dialog.showModal !== "function") return;
    window.tmadsConfirmReady = true;
    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (bypass === form) { bypass = null; return; }
      var source = event.submitter && event.submitter.dataset.confirmMessage ? event.submitter.dataset : form.dataset;
      if (!source.confirmMessage) return;
      event.preventDefault();
      if (dialog.open) return;
      pending = { form:form, submitter:event.submitter, focus:document.activeElement };
      dialog.querySelector("#ui-confirm-title").textContent = source.confirmTitle || "تأیید عملیات";
      dialog.querySelector("#ui-confirm-description").textContent = source.confirmMessage;
      var confirmButton = dialog.querySelector("[data-confirm-action]");
      confirmButton.textContent = source.confirmLabel || "تأیید";
      var primary = source.confirmTone === "primary";
      confirmButton.classList.toggle("btn-primary", primary);
      confirmButton.classList.toggle("btn-danger", !primary);
      dialog.classList.toggle("ui-dialog--primary", primary);
      dialog.returnValue = "cancel";
      dialog.showModal();
    }, true);
    dialog.addEventListener("cancel", function () { dialog.returnValue = "cancel"; });
    dialog.addEventListener("close", function () {
      var action = pending;
      pending = null;
      if (!action) return;
      if (dialog.returnValue === "confirm" && action.form.isConnected) {
        bypass = action.form;
        try {
          if (action.submitter && action.submitter.form === action.form) action.form.requestSubmit(action.submitter);
          else action.form.requestSubmit();
        } finally { bypass = null; }
      }
      if (action.focus && action.focus.isConnected) action.focus.focus();
    });
    dialog.addEventListener("click", function (event) {
      if (event.target !== dialog) return;
      var r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close("cancel");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
