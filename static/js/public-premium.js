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
    // Password eye toggle is handled by ui-auth.js (icon-only).
    var search = root.querySelector('[data-pp-faq-search]');
    if (search && !root.classList.contains('orbit-faq')) {
      var input = search.querySelector('input');
      var count = search.querySelector('[data-pp-faq-count]');
      var cards = Array.from(root.querySelectorAll('.ui-faq-layout .ui-public-faq details'));
      var normalize = function(value) { return value.normalize('NFKC').toLowerCase().replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u200d]/g,' ').replace(/\s+/g,' ').trim(); };
      search.hidden = false;
      function filter() {
        var q = normalize(input.value);
        var tokens = q.split(' ').filter(Boolean);
        var visible = 0;
        cards.forEach(function(card) {
          var haystack = normalize(card.textContent);
          var found = tokens.every(function(token){return haystack.indexOf(token) !== -1;});
          card.hidden = !found;
          if (found) visible++;
        });
        count.textContent = q ? visible.toLocaleString('fa-IR') + ' پرسش مطابق جستجو' : 'همه پرسش‌ها';
      }
      input.addEventListener('input', filter);
      search.addEventListener('submit', function(e){e.preventDefault();});
      search.querySelector('button').addEventListener('click',function(){input.value='';filter();input.focus();});
      filter();
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