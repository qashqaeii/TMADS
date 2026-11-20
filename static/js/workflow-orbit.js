/* Workflow motion and local, non-persistent educational checklist. */
(function () {
  'use strict';
  const root = document.querySelector('body.orbit-workflow');
  if (!root) return;
  const page = root.querySelector('.wf-page');
  const header = root.querySelector('.ui-public-header');
  const scene = page && page.querySelector('.wf-hero-scene');
  if (!page || !header || !scene) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const seen = new WeakSet(), playing = new Set();
  const anchors = Array.from(page.querySelectorAll('.wf-section-nav a'));
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
    page.querySelectorAll('[data-wf-reveal]').forEach(el => {if (!seen.has(el)) observer.observe(el);});
  }
  function syncScroll() {
    frame = 0;
    const y = Math.max(0, window.scrollY || 0);
    header.classList.toggle('wf-nav-scrolled', y > 30);
    const threshold = header.getBoundingClientRect().bottom + 120;
    let index = -1;
    sections.forEach((section,i) => {if(section && section.getBoundingClientRect().top <= threshold) index=i;});
    anchors.forEach((a,i) => {if(i===index) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current');});
    if (!reduced.matches) {
      const range = document.documentElement.scrollHeight - window.innerHeight;
      header.style.setProperty('--wf-scroll', String(range > 0 ? Math.min(1,y/range) : 0));
    }
  }
  function schedule() {if (!frame) frame=requestAnimationFrame(syncScroll);}
  function clearCard() {
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame=0; pointer=null;
    if(card){card.classList.remove('wf-spot-active');card.style.removeProperty('--wf-x');card.style.removeProperty('--wf-y');}
    card=null;
  }
  function moveCard(event) {
    if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
    const target = event.target.closest('.wf-glass');
    if(!target || !page.contains(target)){clearCard();return;}
    if(card!==target){clearCard(); card=target;}
    pointer={x:event.clientX,y:event.clientY};
    if(!pointerFrame) pointerFrame=requestAnimationFrame(()=>{
      pointerFrame=0;
      if(!card || !pointer || reduced.matches) return;
      const box=card.getBoundingClientRect();
      if(!box.width || !box.height) return;
      card.style.setProperty('--wf-x',Math.max(0,Math.min(100,(pointer.x-box.left)/box.width*100))+'%');
      card.style.setProperty('--wf-y',Math.max(0,Math.min(100,(pointer.y-box.top)/box.height*100))+'%');
      card.classList.add('wf-spot-active');
    });
  }
  function clearScene(){
    if(sceneFrame) cancelAnimationFrame(sceneFrame);
    sceneFrame=0;scenePoint=null;
    scene.style.removeProperty('--wf-scene-x');scene.style.removeProperty('--wf-scene-y');
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
      scene.style.setProperty('--wf-scene-x',(bounded(2*(scenePoint.x-box.left)/box.width-1)*7)+'px');
      scene.style.setProperty('--wf-scene-y',(bounded(2*(scenePoint.y-box.top)/box.height-1)*5)+'px');
    });
  }
  function resetMotion(){
    clearCard(); clearScene();
    Array.from(playing).forEach(a=>a.cancel());
  }
  function bootChecklist() {
    const progress=page.querySelector('[data-wf-progress]');
    const checks=Array.from(page.querySelectorAll('[data-wf-check]'));
    if (!progress || !checks.length) return;
    const count=progress.querySelector('[data-wf-count]');
    const bar=progress.querySelector('progress');
    const reset=progress.querySelector('[data-wf-reset]');
    if (!count || !bar || !reset) return;
    function update() {
      const done=checks.filter(input=>input.checked).length;
      bar.max=checks.length;
      bar.value=done;
      count.textContent=done.toLocaleString('fa-IR')+' از '+checks.length.toLocaleString('fa-IR');
      checks.forEach(input=>input.closest('.wf-check-item').classList.toggle('wf-checked',input.checked));
    }
    checks.forEach(input=>{
      input.closest('.wf-check-control').hidden=false;
      input.addEventListener('change',update);
    });
    reset.addEventListener('click',()=>{
      checks.forEach(input=>{input.checked=false;});
      update();
      reset.focus();
    });
    update();
    progress.hidden=false;
  }
  bootChecklist();
  root.classList.add('wf-motion-ready');
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
      observer=null;resetMotion();header.style.removeProperty('--wf-scroll');
    }else{observe();schedule();}
  });
  if(fine.addEventListener) fine.addEventListener('change',()=>{if(!fine.matches){clearCard();clearScene();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)resetMotion();else schedule();});
}());
