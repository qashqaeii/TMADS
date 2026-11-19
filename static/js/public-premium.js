/* Cosmetic motion only; all text is visible before and without JavaScript. */
(function () {
  'use strict';
  function boot() {
    var root = document.querySelector('.public-premium');
    if (!root) return;
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!reduced.matches && 'IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (!entry.isIntersecting) return;
          observer.unobserve(entry.target);
          if (!reduced.matches && !entry.target.contains(document.activeElement)) {
            entry.target.classList.add('pp-enter');
          }
        });
      }, {threshold: 0.06});
      root.querySelectorAll('[data-pp-reveal], .ui-landing-section-head, .ui-editorial-head').forEach(function(el){observer.observe(el);});
    }
    root.querySelectorAll('details.ui-pp-faq-item, .ui-public-faq details').forEach(function(el){
      el.addEventListener('toggle',function(){
        var answer = el.querySelector('p');
        if (!answer || !el.open || reduced.matches || typeof answer.animate !== 'function') return;
        answer.animate([{opacity:.6,transform:'translateY(-3px)'},{opacity:1,transform:'translateY(0)'}],{duration:200,easing:'ease-out'});
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',boot,{once:true}); else boot();
}());