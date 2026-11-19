(function () {
  "use strict";
  function node(tag, cls, text) {
    var el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;
  }
  function init(root) {
    var button=root.querySelector("[data-ai-generate]"), label=root.querySelector("[data-ai-label]"),
        status=root.querySelector("[data-ai-status]"), results=root.querySelector("[data-ai-results]"),
        form=root.closest("form")||root.querySelector("form"), csrf=form&&form.querySelector("[name=csrfmiddlewaretoken]"),
        editor=form&&form.querySelector("[name=ad_text]"), brief=root.querySelector("[data-ai-brief]");
    if(!button||!label||!status||!results||!csrf)return;
    if(brief){["input","change"].forEach(function(event){brief.addEventListener(event,function(e){e.stopPropagation();});});}
    root.hidden=false;
    button.addEventListener("click",async function(){
      if(button.disabled)return;
      if(editor && !editor.value.trim() && brief && !brief.value.trim()){status.textContent="توضیح کوتاهی وارد کنید.";brief.focus();return;}
      var original=label.textContent;button.disabled=true;label.textContent="در حال آماده‌سازی…";
      root.setAttribute("aria-busy","true");status.textContent="در حال دریافت پیشنهاد…";
      results.hidden=true;results.replaceChildren();
      var data=new URLSearchParams();
      if(brief)data.set("brief",brief.value);if(editor)data.set("current",editor.value);
      data.set("csrfmiddlewaretoken",csrf.value);
      var controller=new AbortController(), timeout=setTimeout(function(){controller.abort();},25000);
      try{
        var response=await fetch(root.dataset.aiUrl,{method:"POST",body:data,credentials:"same-origin",signal:controller.signal,headers:{"Accept":"application/json"}});
        var payload=await response.json();
        if(!response.ok||!payload.ok){status.textContent=payload.message||"دریافت پیشنهاد ممکن نیست.";return;}
        if(root.dataset.tmAi==="creative"&&editor&&Array.isArray(payload.variants)){
          payload.variants.forEach(function(text,i){
            if(typeof text!=="string")return;
            var card=node("article","tm-ai-option"), head=node("div","tm-ai-option-head");
            head.append(node("strong","", "پیشنهاد "+(i+1).toLocaleString("fa-IR")),node("small","",Array.from(text).length.toLocaleString("fa-IR")+" / ۱۶۰"));
            var copy=node("p","",text), apply=node("button","btn btn-ghost","انتخاب متن");
            apply.type="button";apply.addEventListener("click",function(){
              editor.value=text;editor.dispatchEvent(new Event("input",{bubbles:true}));editor.dispatchEvent(new Event("change",{bubbles:true}));
              status.textContent="پیشنهاد در پیش‌نویس قرار گرفت.";editor.focus();
            });card.append(head,copy,apply);results.append(card);
          });
        }
        if(!results.childElementCount){status.textContent="پیشنهاد قابل استفاده‌ای دریافت نشد.";return;}
        results.hidden=false;status.textContent=payload.cached?"پیشنهاد ذخیره‌شده نمایش داده شد.":"پیشنهاد آماده است؛ قبل از استفاده آن را مرور کنید.";
      }catch(e){status.textContent="ارتباط با دستیار برقرار نشد. بدون دستیار ادامه دهید.";}
      finally{clearTimeout(timeout);button.disabled=false;label.textContent=original;root.removeAttribute("aria-busy");}
    });
  }
  function boot(){document.querySelectorAll("[data-tm-ai]").forEach(init);}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();