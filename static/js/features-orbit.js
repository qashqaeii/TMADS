/* Features-only motion; native links and content are always available. */
(function () {
  'use strict';
  const root = document.querySelector('body.orbit-features');
  if (!root) return;
  const page = root.querySelector('.fx-page');
  const header = root.querySelector('.ui-public-header');
  const scene = page && page.querySelector('.fx-hero-visual');
  if (!page || !header || !scene) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const seen = new WeakSet(), playing = new Set();
  const anchors = Array.from(page.querySelectorAll('.fx-section-nav a'));
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
    page.querySelectorAll('[data-fx-reveal]').forEach(el => {if (!seen.has(el)) observer.observe(el);});
  }
  function syncScroll() {
    frame = 0;
    const y = Math.max(0, window.scrollY || 0);
    header.classList.toggle('fx-nav-scrolled', y > 30);
    const threshold = header.getBoundingClientRect().bottom + 120;
    let index = -1;
    sections.forEach((section,i) => {if(section && section.getBoundingClientRect().top <= threshold) index=i;});
    anchors.forEach((a,i) => {if(i===index) a.setAttribute('aria-current','location'); else a.removeAttribute('aria-current');});
    if (!reduced.matches) {
      const range = document.documentElement.scrollHeight - window.innerHeight;
      header.style.setProperty('--fx-scroll', String(range > 0 ? Math.min(1,y/range) : 0));
    }
  }
  function schedule() {if (!frame) frame=requestAnimationFrame(syncScroll);}
  function clearCard() {
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame=0; pointer=null;
    if(card){card.classList.remove('fx-spot-active');card.style.removeProperty('--fx-x');card.style.removeProperty('--fx-y');}
    card=null;
  }
  function moveCard(event) {
    if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
    const target = event.target.closest('.fx-card');
    if(!target || !page.contains(target)){clearCard();return;}
    if(card!==target){clearCard(); card=target;}
    pointer={x:event.clientX,y:event.clientY};
    if(!pointerFrame) pointerFrame=requestAnimationFrame(()=>{
      pointerFrame=0;
      if(!card || !pointer || reduced.matches) return;
      const box=card.getBoundingClientRect();
      if(!box.width || !box.height) return;
      card.style.setProperty('--fx-x',Math.max(0,Math.min(100,(pointer.x-box.left)/box.width*100))+'%');
      card.style.setProperty('--fx-y',Math.max(0,Math.min(100,(pointer.y-box.top)/box.height*100))+'%');
      card.classList.add('fx-spot-active');
    });
  }
  function clearScene(){
    if(sceneFrame) cancelAnimationFrame(sceneFrame);
    sceneFrame=0;scenePoint=null;
    scene.style.removeProperty('--fx-scene-x');scene.style.removeProperty('--fx-scene-y');
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
      scene.style.setProperty('--fx-scene-x',(bounded(2*(scenePoint.x-box.left)/box.width-1)*7)+'px');
      scene.style.setProperty('--fx-scene-y',(bounded(2*(scenePoint.y-box.top)/box.height-1)*5)+'px');
    });
  }
  function resetMotion(){
    clearCard(); clearScene();
    Array.from(playing).forEach(a=>a.cancel());
  }
  root.classList.add('fx-motion-ready');
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
      observer=null;resetMotion();header.style.removeProperty('--fx-scroll');
    }else{observe();schedule();}
  });
  if(fine.addEventListener) fine.addEventListener('change',()=>{if(!fine.matches){clearCard();clearScene();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)resetMotion();else schedule();});
}());
