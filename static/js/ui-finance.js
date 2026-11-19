(function () {
  "use strict";
  function boot() {
    var status=document.querySelector("[data-pay-copy-status]");
    if (status && navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      document.querySelectorAll("[data-pay-copy]").forEach(function(button){
        var target=document.getElementById(button.dataset.payCopy);
        if(!target)return;
        button.hidden=false;
        button.addEventListener("click",function(){
          navigator.clipboard.writeText(target.textContent.trim()).then(function(){
            status.hidden=false;status.textContent="شناسه کپی شد.";
          }).catch(function(){
            status.hidden=false;status.textContent="کپی خودکار ممکن نیست؛ شناسه را انتخاب و کپی کنید.";
          });
        });
      });
    }
    var recheck=document.querySelector("[data-pay-recheck]");
    if(recheck){
      var checkButton=recheck.querySelector("button[type=submit]"),checkLabel=recheck.querySelector("[data-pay-submit-label]");
      recheck.addEventListener("submit",function(event){
        if(checkButton.disabled){event.preventDefault();return;}
        checkButton.disabled=true;checkLabel.textContent="در حال بررسی…";
      });
      window.addEventListener("pageshow",function(event){
        if(event.persisted){checkButton.disabled=false;checkLabel.textContent="بررسی مجدد وضعیت";}
      });
    }
    var form=document.querySelector("[data-topup-form]");
    if (!form) return;
    var input=form.querySelector("#topup-amount"), row=form.querySelector("[data-quick-amounts]"), total=form.querySelector("[data-topup-total]");
    if (!input || !row || !total) return;
    row.hidden=false; total.hidden=false;
    var quickBox=form.querySelector("[data-quick-amounts-box]"); if(quickBox)quickBox.hidden=false;
    function update() {
      var amount=Number(input.value);
      total.querySelector("[data-topup-value]").textContent=input.value && Number.isSafeInteger(amount) && amount>=1000 ? amount.toLocaleString("fa-IR")+" تومان" : "—";
      row.querySelectorAll("[data-amount]").forEach(function(button){button.setAttribute("aria-pressed",String(input.value!=="" && Number(button.dataset.amount)===amount));});
    }
    row.addEventListener("click",function(event){var b=event.target.closest("[data-amount]");if(!b)return;input.value=b.dataset.amount;input.dispatchEvent(new Event("input",{bubbles:true}));input.focus();});
    input.addEventListener("input",update);update();
    var submit=form.querySelector("[data-payment-submit]");
    if(submit){form.addEventListener("submit",function(e){if(submit.disabled){e.preventDefault();return;}submit.disabled=true;(submit.querySelector("[data-pay-submit-label]")||submit).textContent="در حال آماده‌سازی پرداخت…";});window.addEventListener("pageshow",function(e){if(e.persisted){submit.disabled=false;(submit.querySelector("[data-pay-submit-label]")||submit).textContent="ادامه پرداخت";}});}
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();
