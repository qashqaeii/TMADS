/* Pricing-only motion and educational calculator. No requests or finance writes. */
(function () {
  'use strict';
  const root = document.querySelector('body.orbit-pricing');
  if (!root) return;
  const page = root.querySelector('.pr-page');
  const header = root.querySelector('.ui-public-header');
  const scene = page && page.querySelector('.pr-hero-scene');
  if (!page || !header || !scene) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const seen = new WeakSet(), playing = new Set();
  const anchors = Array.from(page.querySelectorAll('.pr-section-nav a'));
  const sections = anchors.map(link => document.getElementById(link.hash.slice(1)));
  let observer, frame = 0, pointerFrame = 0, card = null, pointer = null;
  let sceneFrame = 0, scenePoint = null;
  function enter(el) {
    if (seen.has(el)) return;
    seen.add(el);
    if (observer) observer.unobserve(el);
    if (reduced.matches || document.hidden || !el.animate || el.contains(document.activeElement)) return;
    const index = Array.prototype.indexOf.call(el.parentElement.children, el);
    const animation = el.animate([
      {opacity: .76, transform: 'translate3d(0,15px,0)'},
      {opacity: 1, transform: 'translate3d(0,0,0)'}
    ], {duration: 650, delay: Math.min(index,3)*55, easing:'cubic-bezier(.18,.76,.24,1)'});
    playing.add(animation);
    animation.onfinish = animation.oncancel = () => playing.delete(animation);
  }
  function observe() {
    if (reduced.matches || observer || !('IntersectionObserver' in window)) return;
    observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {if (entry.isIntersecting) enter(entry.target);});
    }, {threshold:.08});
    page.querySelectorAll('[data-pr-reveal]').forEach(el => {if (!seen.has(el)) observer.observe(el);});
  }
  function syncScroll() {
    frame = 0;
    const y = Math.max(0, window.scrollY || 0);
    header.classList.toggle('pr-nav-scrolled', y > 30);
    const threshold = header.getBoundingClientRect().bottom + 120;
    let index = -1;
    sections.forEach((section,i) => {if(section && section.getBoundingClientRect().top <= threshold) index=i;});
    anchors.forEach((a,i) => {if(i===index) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current');});
    if (!reduced.matches) {
      const range = document.documentElement.scrollHeight - window.innerHeight;
      header.style.setProperty('--pr-scroll', String(range > 0 ? Math.min(1,y/range) : 0));
    }
  }
  function schedule() {if (!frame) frame=requestAnimationFrame(syncScroll);}
  function clearCard() {
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame=0; pointer=null;
    if(card){card.classList.remove('pr-spot-active');card.style.removeProperty('--pr-x');card.style.removeProperty('--pr-y');}
    card=null;
  }
  function moveCard(event) {
    if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
    const target = event.target.closest('.pr-glass');
    if(!target || !page.contains(target)){clearCard();return;}
    if(card!==target){clearCard(); card=target;}
    pointer={x:event.clientX,y:event.clientY};
    if(!pointerFrame) pointerFrame=requestAnimationFrame(()=>{
      pointerFrame=0;
      if(!card || !pointer || reduced.matches) return;
      const box=card.getBoundingClientRect();
      if(!box.width || !box.height) return;
      card.style.setProperty('--pr-x',Math.max(0,Math.min(100,(pointer.x-box.left)/box.width*100))+'%');
      card.style.setProperty('--pr-y',Math.max(0,Math.min(100,(pointer.y-box.top)/box.height*100))+'%');
      card.classList.add('pr-spot-active');
    });
  }
  function clearScene(){
    if(sceneFrame) cancelAnimationFrame(sceneFrame);
    sceneFrame=0;scenePoint=null;
    scene.style.removeProperty('--pr-scene-x');scene.style.removeProperty('--pr-scene-y');
  }
  function moveScene(event){
    if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
    scenePoint={x:event.clientX,y:event.clientY};
    if(!sceneFrame) sceneFrame=requestAnimationFrame(()=>{
      sceneFrame=0;
      if(!scenePoint || reduced.matches) return;
      const box=scene.getBoundingClientRect();
      if(!box.width || !box.height) return;
      const bounded=n=>Math.max(-1,Math.min(1,n));
      scene.style.setProperty('--pr-scene-x',(bounded(2*(scenePoint.x-box.left)/box.width-1)*7)+'px');
      scene.style.setProperty('--pr-scene-y',(bounded(2*(scenePoint.y-box.top)/box.height-1)*5)+'px');
    });
  }
  function resetMotion(){
    clearCard(); clearScene();
    Array.from(playing).forEach(a=>a.cancel());
  }

  // Fixed-point math: input values in millionths; output stays exact for
  // valid inputs, including Persian decimal separators and fractional CPM.
  function bootCalculator() {
    const panel=page.querySelector('[data-pr-calculator]');
    const example=page.querySelector('#pr-calc-example');
    if (!panel || !example || typeof BigInt !== 'function') return;
    const budget=panel.querySelector('#pr-budget'), cpm=panel.querySelector('#pr-cpm');
    const impressions=panel.querySelector('#pr-impressions');
    const viewOutput=panel.querySelector('#pr-view-result'), costOutput=panel.querySelector('#pr-cost-result');
    const error=panel.querySelector('[data-pr-error]');
    const scale=1000000n, limit=1000000000n;
    const faDigits='۰۱۲۳۴۵۶۷۸۹', arDigits='٠١٢٣٤٥٦٧٨٩';
    function normalize(raw) {
      return raw.trim().replace(/[۰-۹]/g,ch=>String(faDigits.indexOf(ch)))
        .replace(/[٠-٩]/g,ch=>String(arDigits.indexOf(ch))).replace(/٫/g,'.');
    }
    function parse(raw, integerOnly) {
      const value=normalize(raw);
      if (!/^(?:\d+|\d{1,3}(?:[,٬]\d{3})+)(?:\.\d{1,6})?$/.test(value)) return null;
      const parts=value.replace(/[,٬]/g,'').split('.');
      if (integerOnly && parts.length>1) return null;
      const number=BigInt(parts[0])*scale + BigInt((parts[1]||'').padEnd(6,'0'));
      return number<=limit*scale ? number : null;
    }
    function localize(raw) {return raw.replace(/\d/g,ch=>faDigits[Number(ch)]);}
    function format(value, decimals=0) {
      let raw=value.toString().padStart(decimals+1,'0');
      const integer=decimals?raw.slice(0,-decimals):raw;
      const fraction=decimals?raw.slice(-decimals).replace(/0+$/,''):'';
      return localize(integer.replace(/\B(?=(\d{3})+(?!\d))/g,'٬')+(fraction?'٫'+fraction:''));
    }
    function validate(input,valid) {
      if(valid) input.removeAttribute('aria-invalid');
      else input.setAttribute('aria-invalid','true');
    }
    function update() {
      const b=parse(budget.value,false), c=parse(cpm.value,false), n=parse(impressions.value,true);
      const cValid=c!==null && c>0n;
      validate(budget,b!==null);validate(cpm,cValid);validate(impressions,n!==null);
      // Floor impressions: zero budget is valid, a zero or malformed CPM is not.
      viewOutput.textContent=b!==null&&cValid?format(b*1000n/c):'—';
      // n is scaled by 1e6, c by 1e6; cost = n_real*c_real/1000.
      costOutput.textContent=n!==null&&cValid?format((n/scale)*c,9):'—';
      const invalid=b===null||!cValid||n===null;
      error.textContent=invalid?'مقدار فیلدهای مشخص‌شده را بررسی کنید؛ تعداد نمایش باید عدد صحیح و CPM مثبت باشد.':'';
      error.hidden=!invalid;
    }
    [budget,cpm,impressions].forEach(input=>input.addEventListener('input',update));
    panel.querySelector('[data-pr-reset]').addEventListener('click',()=>{
      budget.value='۲۰';cpm.value='۲';impressions.value='۱۰٬۰۰۰';update();budget.focus();
    });
    update();
    panel.hidden=false;
    example.hidden=true;
  }
  bootCalculator();

  root.classList.add('pr-motion-ready');
  observe(); schedule();
  window.addEventListener('scroll',schedule,{passive:true});
  window.addEventListener('resize',schedule,{passive:true});
  page.addEventListener('pointermove',moveCard,{passive:true});
  page.addEventListener('pointerleave',clearCard);
  scene.addEventListener('pointermove',moveScene,{passive:true});
  scene.addEventListener('pointerleave',clearScene);
  if(reduced.addEventListener) reduced.addEventListener('change',()=>{
    if(reduced.matches){
      if(observer) observer.disconnect();
      observer=null;resetMotion();header.style.removeProperty('--pr-scroll');
    }else{observe();schedule();}
  });
  if(fine.addEventListener) fine.addEventListener('change',()=>{if(!fine.matches){clearCard();clearScene();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)resetMotion();else schedule();});
}());
