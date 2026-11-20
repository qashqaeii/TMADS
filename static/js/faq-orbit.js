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
  const normalize=value=>value.normalize('NFKC').toLowerCase().replace(/ي|ى/g,'ی').replace(/ك/g,'ک').replace(/[\u200c\u200d]/g,' ').replace(/[\u064b-\u065f\u0670]/g,'').replace(/\s+/g,' ').trim();
  let active='all';
  const number=n=>n.toLocaleString('fa-IR');
  function filter(){
    const tokens=normalize(input.value).split(' ').filter(Boolean);
    let total=0;
    groups.forEach(group=>{
      let visible=0;
      group.querySelectorAll('[data-fq-question]').forEach(question=>{
        const found=(active==='all'||group.dataset.fqGroup===active)&&tokens.every(token=>normalize(question.textContent).includes(token));
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
