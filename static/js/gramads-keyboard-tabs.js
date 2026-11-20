/* Preserve Alpine's actual click handlers and chart resizing; add accessible tab navigation. */
(function(){
  "use strict";
  document.addEventListener("keydown",function(event){
    if(!(event.target instanceof Element))return;
    const source=event.target.closest('[role="tab"]');
    const list=source&&source.closest("[data-ga-keyboard-tabs]");
    if(!list||!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;
    const tabs=Array.from(list.querySelectorAll('[role="tab"]:not([disabled])'));
    const current=tabs.indexOf(source);if(current<0)return;
    const rtl=getComputedStyle(list).direction==="rtl";
    let next=event.key==="Home"?0:event.key==="End"?tabs.length-1:(current+(event.key==="ArrowLeft"?(rtl?1:-1):(rtl?-1:1))+tabs.length)%tabs.length;
    event.preventDefault();tabs[next].click();tabs[next].focus();
  });
})();