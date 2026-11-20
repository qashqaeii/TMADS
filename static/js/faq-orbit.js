/* Local FAQ search only. No network, storage or personal data. */
(function () {
  'use strict';
  const page=document.querySelector('body.orbit-faq .fq-page');
  if(!page) return;
  const form=page.querySelector('[data-pp-faq-search]'), input=form.querySelector('input');
  const count=form.querySelector('[data-pp-faq-count]'), categories=page.querySelector('[data-fq-categories]');
  const buttons=Array.from(categories.querySelectorAll('[data-fq-category]'));
  const groups=Array.from(page.querySelectorAll('[data-fq-group]'));
  const empty=page.querySelector('[data-fq-empty]');
  const normalize=value=>value.normalize('NFKC').toLowerCase().replace(/ي|ى/g,'ی').replace(/ك/g,'ک').replace(/ؤ/g,'و').replace(/[\u200c\u200d]/g,' ').replace(/[\u064b-\u065f\u0670]/g,'').replace(/\s+/g,' ').trim();
  let active='all';
  const number=n=>n.toLocaleString('fa-IR');
  function filter(){
    const tokens=normalize(input.value).split(' ').filter(Boolean);
    let total=0;
    groups.forEach(group=>{
      let visible=0;
      group.querySelectorAll('[data-fq-question]').forEach(question=>{
        const found=(active==='all'||group.dataset.fqGroup===active)&&tokens.every(token=>normalize(question.querySelector('summary').textContent+' '+question.querySelector('p').textContent).includes(token));
        question.hidden=!found;
        if(found) visible++;
      });
      group.hidden=!visible;
      group.querySelector('.fq-group-head span').textContent=number(visible)+' پرسش';
      total+=visible;
    });
    count.textContent=number(total)+(tokens.length?' پرسش مطابق جست‌وجو':' پرسش');
    empty.hidden=total!==0;
    buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.fqCategory===active)));
  }
  input.addEventListener('input',filter);
  form.addEventListener('submit',event=>event.preventDefault());
  form.querySelector('[data-fq-clear]').addEventListener('click',()=>{input.value='';filter();input.focus();});
  buttons.forEach(button=>button.addEventListener('click',()=>{active=button.dataset.fqCategory;filter();}));
  empty.querySelector('[data-fq-reset]').addEventListener('click',()=>{active='all';input.value='';filter();input.focus();});
  form.hidden=false;categories.hidden=false;page.querySelector('[data-fq-static]').hidden=true;filter();
}());

/* FAQ-only progressive motion and native accordion enhancement. */
(function () {
  'use strict';
  const root = document.querySelector('body.orbit-faq');
  if (!root) return;
  const page = root.querySelector('.fq-page');
  const header = root.querySelector('.ui-public-header');
  const scene = page && page.querySelector('.fq-hero-scene');
  if (!page || !header || !scene) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  const seen = new WeakSet(), playing = new Set();
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
    page.querySelectorAll('[data-fq-reveal]').forEach(el => {if (!seen.has(el)) observer.observe(el);});
  }
  function syncScroll() {
    frame = 0;
    const y = Math.max(0, window.scrollY || 0);
    header.classList.toggle('fq-nav-scrolled', y > 30);
    if (!reduced.matches) {
      const range = document.documentElement.scrollHeight - window.innerHeight;
      header.style.setProperty('--fq-scroll', String(range > 0 ? Math.min(1,y/range) : 0));
    }
  }
  function schedule() {if (!frame) frame=requestAnimationFrame(syncScroll);}
  function clearCard() {
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame=0; pointer=null;
    if(card){card.classList.remove('fq-spot-active');card.style.removeProperty('--fq-x');card.style.removeProperty('--fq-y');}
    card=null;
  }
  function moveCard(event) {
    if(reduced.matches || !fine.matches || event.pointerType==='touch') return;
    const target = event.target.closest('.fq-glass');
    if(!target || !page.contains(target)){clearCard();return;}
    if(card!==target){clearCard(); card=target;}
    pointer={x:event.clientX,y:event.clientY};
    if(!pointerFrame) pointerFrame=requestAnimationFrame(()=>{
      pointerFrame=0;
      if(!card || !pointer || reduced.matches) return;
      const box=card.getBoundingClientRect();
      if(!box.width || !box.height) return;
      card.style.setProperty('--fq-x',Math.max(0,Math.min(100,(pointer.x-box.left)/box.width*100))+'%');
      card.style.setProperty('--fq-y',Math.max(0,Math.min(100,(pointer.y-box.top)/box.height*100))+'%');
      card.classList.add('fq-spot-active');
    });
  }
  function clearScene(){
    if(sceneFrame) cancelAnimationFrame(sceneFrame);
    sceneFrame=0;scenePoint=null;
    scene.style.removeProperty('--fq-scene-x');scene.style.removeProperty('--fq-scene-y');
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
      scene.style.setProperty('--fq-scene-x',(bounded(2*(scenePoint.x-box.left)/box.width-1)*7)+'px');
      scene.style.setProperty('--fq-scene-y',(bounded(2*(scenePoint.y-box.top)/box.height-1)*5)+'px');
    });
  }
  function resetMotion(){
    clearCard(); clearScene();
    Array.from(playing).forEach(a=>a.cancel());
  }
  page.querySelectorAll('[data-fq-question]').forEach(question=>{
    question.addEventListener('toggle',()=>{
      if(!question.open || reduced.matches || document.hidden) return;
      const answer=question.querySelector('p');
      if(!answer || !answer.animate) return;
      const animation=answer.animate([{opacity:.55,transform:'translateY(-4px)'},{opacity:1,transform:'translateY(0)'}],{duration:240,easing:'cubic-bezier(.2,.8,.2,1)'});
      playing.add(animation);
      animation.onfinish=animation.oncancel=()=>playing.delete(animation);
    });
  });
  root.classList.add('fq-motion-ready');
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
      observer=null;resetMotion();header.style.removeProperty('--fq-scroll');
    }else{observe();schedule();}
  });
  if(fine.addEventListener) fine.addEventListener('change',()=>{if(!fine.matches){clearCard();clearScene();}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)resetMotion();else schedule();});
}());
