/* Password visibility is optional UI only (does not read, store or transmit values). */
(function () {
  "use strict";
  function boot() {
    document.querySelectorAll('.ui-auth-card input[type="password"], .ui-account-page input[type="password"]').forEach(function (input) {
      if (input.closest(".ui-password-wrap, .pp-password-row")) return;
      var wrap=document.createElement("div"), button=document.createElement("button");
      wrap.className="ui-password-wrap";input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);
      button.type="button";button.className="ui-password-toggle";button.textContent="نمایش";button.setAttribute("aria-label","نمایش رمز عبور");button.setAttribute("aria-pressed","false");if(input.id)button.setAttribute("aria-controls",input.id);wrap.appendChild(button);
      button.addEventListener("click",function(){var show=input.type==="password";input.type=show?"text":"password";button.textContent=show?"پنهان":"نمایش";button.setAttribute("aria-pressed",String(show));button.setAttribute("aria-label",show?"پنهان کردن رمز عبور":"نمایش رمز عبور");});
    });
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
