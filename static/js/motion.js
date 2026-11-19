/** Content remains visible regardless of JS or scroll position. */
(function(){
  function reveal(root){
    if(!root)return;
    if(root.classList && root.classList.contains("motion-reveal"))root.classList.add("is-revealed");
    root.querySelectorAll(".motion-reveal").forEach(function(el){el.classList.add("is-revealed");});
  }
  window.tmadsRevealIn=reveal;
  function boot(){reveal(document);}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
  document.addEventListener("alpine:initialized",boot);
  document.addEventListener("htmx:afterSettle",boot);
})();
