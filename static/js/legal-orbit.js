/* Legal reading enhancements. Every clause is visible without JavaScript. */
(function(){
  'use strict';
  const page=document.querySelector('body.orbit-legal .lg-page');
  if(!page)return;
  const print=page.querySelector('[data-legal-print]');
  if(print&&typeof window.print==='function'){
    print.hidden=false;
    print.addEventListener('click',()=>window.print());
  }
  const links=Array.from(page.querySelectorAll('[data-legal-section-link]'));
  const sections=links.map(link=>document.getElementById(link.hash.slice(1)));
  const header=document.querySelector('.ui-public-header');
  let frame=0;
  function sync(){
    frame=0;
    const threshold=(header?header.getBoundingClientRect().bottom:0)+35;
    let active=0;
    sections.forEach((section,i)=>{if(section&&section.getBoundingClientRect().top<=threshold)active=i;});
    links.forEach((link,i)=>{if(i===active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});
  }
  function schedule(){if(!frame)frame=requestAnimationFrame(sync);}
  window.addEventListener('scroll',schedule,{passive:true});
  window.addEventListener('resize',schedule,{passive:true});
  schedule();
}());
