(function () {
  "use strict";
  function boot() {
    var form=document.querySelector("[data-topup-form]");
    if (!form) return;
    var input=form.querySelector("#topup-amount"), row=form.querySelector("[data-quick-amounts]"), total=form.querySelector("[data-topup-total]");
    if (!input || !row || !total) return;
    row.hidden=false; total.hidden=false;
    function update() {
      var amount=Number(input.value);
      total.querySelector("[data-topup-value]").textContent=input.value && Number.isSafeInteger(amount) && amount>=1000 ? amount.toLocaleString("fa-IR")+" تومان" : "—";
      row.querySelectorAll("[data-amount]").forEach(function(button){button.setAttribute("aria-pressed",String(input.value!=="" && Number(button.dataset.amount)===amount));});
    }
    row.addEventListener("click",function(event){var b=event.target.closest("[data-amount]");if(!b)return;input.value=b.dataset.amount;input.dispatchEvent(new Event("input",{bubbles:true}));input.focus();});
    input.addEventListener("input",update);update();
    var submit=form.querySelector("[data-payment-submit]");
    if(submit){form.addEventListener("submit",function(e){if(submit.disabled){e.preventDefault();return;}submit.disabled=true;submit.textContent="در حال آماده‌سازی پرداخت…";});window.addEventListener("pageshow",function(e){if(e.persisted){submit.disabled=false;submit.textContent="ادامه پرداخت";}});}
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
