/* Password visibility is optional UI only (does not read, store or transmit values). */
(function () {
  "use strict";

  var EYE =
    '<svg class="ui-password-toggle__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.75"/></svg>';
  var EYE_OFF =
    '<svg class="ui-password-toggle__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M17.479 17.499A10.75 10.75 0 0 1 2.062 11.652a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.463-4.8"/><path fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="m2 2 20 20"/></svg>';

  function setToggleIcon(button, show) {
    button.innerHTML = show ? EYE_OFF : EYE;
    button.setAttribute("aria-pressed", String(show));
    button.setAttribute("aria-label", show ? "پنهان کردن رمز عبور" : "نمایش رمز عبور");
  }

  function bindToggle(button, input) {
    setToggleIcon(button, false);
    button.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      setToggleIcon(button, show);
    });
  }

  function boot() {
    document
      .querySelectorAll('.ui-auth-card input[type="password"], .ui-account-page input[type="password"]')
      .forEach(function (input) {
        if (input.closest(".ui-password-wrap, .pp-password-row")) return;
        var wrap = document.createElement("div");
        var button = document.createElement("button");
        wrap.className = "ui-password-wrap";
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);
        button.type = "button";
        button.className = "ui-password-toggle";
        if (input.id) button.setAttribute("aria-controls", input.id);
        wrap.appendChild(button);
        bindToggle(button, input);
      });

    document.querySelectorAll("[data-pp-password-toggle]").forEach(function (button) {
      var input = document.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;
      button.hidden = false;
      bindToggle(button, input);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
