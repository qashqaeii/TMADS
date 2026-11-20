/* Visual animation only; never reads or stores any form value. */
(function(){
  'use strict';
  const root=document.querySelector('body.orbit-auth');
  if(!root)return;
  const scene=root.querySelector('.ao-scene');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  const fine=window.matchMedia('(hover: hover) and (pointer: fine)');
  let frame=0,point=null,animations=[];
  function reset(){
    if(frame)cancelAnimationFrame(frame);
    frame=0;point=null;
    if(scene){scene.style.removeProperty('--ao-x');scene.style.removeProperty('--ao-y');}
    animations.forEach(a=>a.cancel());animations=[];
  }
  if(!reduced.matches&&!document.hidden){
    const aside=root.querySelector('.ao-aside-copy');
    if(aside&&aside.animate)animations.push(aside.animate([{opacity:.6,transform:'translateY(10px)'},{opacity:1,transform:'none'}],{duration:650,easing:'cubic-bezier(.2,.8,.2,1)'}));
  }
  if(scene){
    scene.addEventListener('pointermove',event=>{
      if(reduced.matches||!fine.matches||event.pointerType==='touch')return;
      point={x:event.clientX,y:event.clientY};
      if(!frame)frame=requestAnimationFrame(()=>{
        frame=0;if(!point||reduced.matches)return;
        const b=scene.getBoundingClientRect();if(!b.width||!b.height)return;
        const clamp=n=>Math.max(-1,Math.min(1,n));
        scene.style.setProperty('--ao-x',clamp(2*(point.x-b.left)/b.width-1)*8+'px');
        scene.style.setProperty('--ao-y',clamp(2*(point.y-b.top)/b.height-1)*6+'px');
      });
    },{passive:true});
    scene.addEventListener('pointerleave',reset);
  }
  if(reduced.addEventListener)reduced.addEventListener('change',reset);
  if(fine.addEventListener)fine.addEventListener('change',reset);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();});
  root.classList.add('ao-ready');
}());
