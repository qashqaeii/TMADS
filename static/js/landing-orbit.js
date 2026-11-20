/* Orbit motion: progressive enhancement; content and native navigation never depend on JS. */
(function () {
  'use strict';
  var root = document.querySelector('body.orbit-landing');
  if (!root) return;
  var page = root.querySelector('.orbit-page');
  var header = root.querySelector('.ui-public-header');
  if (!page || !header) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  var active = new Set();
  var observed = new WeakSet();
  var observer;
  var frame = 0;
  var previousScrolled;
  var stageSelector = '.orbit-hero-copy > *, .orbit-hero-figure, .orbit-centered, .orbit-section-copy, .orbit-target, .orbit-step, .orbit-official, .orbit-mini-card, .orbit-guide-card, .orbit-faq-list details, .orbit-faq-scene, .orbit-cta';
  var surfaceSelector = '.orbit-target, .orbit-step, .orbit-mini-card, .orbit-guide-card';
  var scene = page.querySelector('.orbit-hero-scene');
  var currentSurface = null;
  var pointerFrame = 0;
  var pointer = null;
  var sceneFrame = 0;
  var scenePointer = null;

  function play(element, frames, options) {
    if (reduced.matches || !element.animate || document.hidden) return;
    var animation = element.animate(frames, options);
    active.add(animation);
    animation.onfinish = animation.oncancel = function () { active.delete(animation); };
  }
  function enter(element) {
    if (observed.has(element)) return;
    observed.add(element);
    if (observer) observer.unobserve(element);
    if (element.contains(document.activeElement)) return;
    var group = element.parentElement;
    var index = group ? Array.prototype.indexOf.call(group.children, element) : 0;
    var delay = Math.min(Math.max(index, 0), 3) * 65;
    // Visible before JS, while offline, and when motion is reduced.
    play(element, [
      { opacity: .72, transform: 'translate3d(0, 15px, 0)' },
      { opacity: 1, transform: 'translate3d(0, 0, 0)' }
    ], { duration: 660, delay: delay, easing: 'cubic-bezier(.18,.76,.24,1)' });
  }
  function observeEntries() {
    if (reduced.matches || !('IntersectionObserver' in window) || observer) return;
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { if (entry.isIntersecting) enter(entry.target); });
    }, { threshold: .08 });
    page.querySelectorAll(stageSelector).forEach(function (element) {
      if (!observed.has(element)) observer.observe(element);
    });
  }
  function updateScroll() {
    frame = 0;
    var y = Math.max(0, window.scrollY || 0);
    var scrolled = y > 32;
    if (scrolled !== previousScrolled) {
      header.classList.toggle('orbit-nav-scrolled', scrolled);
      previousScrolled = scrolled;
    }
    if (!reduced.matches) {
      var range = document.documentElement.scrollHeight - window.innerHeight;
      var progress = range > 0 ? Math.min(1, y / range) : 0;
      header.style.setProperty('--orbit-scroll', String(progress));
    }
  }
  function scheduleScroll() {
    if (!frame) frame = requestAnimationFrame(updateScroll);
  }
  function clearSurface() {
    if (currentSurface) {
      currentSurface.classList.remove('orbit-spot-active');
      currentSurface.style.removeProperty('--spot-x');
      currentSurface.style.removeProperty('--spot-y');
    }
    currentSurface = null;
    pointer = null;
    if (pointerFrame) cancelAnimationFrame(pointerFrame);
    pointerFrame = 0;
  }
  function updateSurface() {
    pointerFrame = 0;
    if (!pointer || !currentSurface || reduced.matches || !fine.matches) return;
    var rect = currentSurface.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    currentSurface.style.setProperty('--spot-x', Math.max(0, Math.min(100, (pointer.x - rect.left) / rect.width * 100)).toFixed(1) + '%');
    currentSurface.style.setProperty('--spot-y', Math.max(0, Math.min(100, (pointer.y - rect.top) / rect.height * 100)).toFixed(1) + '%');
    currentSurface.classList.add('orbit-spot-active');
  }
  function onSurfaceMove(event) {
    if (reduced.matches || !fine.matches || event.pointerType === 'touch') return;
    var surface = event.target.closest(surfaceSelector);
    if (!surface || !page.contains(surface)) { clearSurface(); return; }
    if (currentSurface !== surface) { clearSurface(); currentSurface = surface; }
    pointer = { x: event.clientX, y: event.clientY };
    if (!pointerFrame) pointerFrame = requestAnimationFrame(updateSurface);
  }
  function clearScene() {
    scenePointer = null;
    if (sceneFrame) cancelAnimationFrame(sceneFrame);
    sceneFrame = 0;
    if (scene) {
      scene.style.removeProperty('--scene-x');
      scene.style.removeProperty('--scene-y');
    }
  }
  function updateScene() {
    sceneFrame = 0;
    if (!scenePointer || !scene || reduced.matches || !fine.matches) return;
    var rect = scene.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    var x = Math.max(-1, Math.min(1, (scenePointer.x - rect.left) / rect.width * 2 - 1));
    var y = Math.max(-1, Math.min(1, (scenePointer.y - rect.top) / rect.height * 2 - 1));
    scene.style.setProperty('--scene-x', (x * 8).toFixed(2) + 'px');
    scene.style.setProperty('--scene-y', (y * 6).toFixed(2) + 'px');
  }
  function onSceneMove(event) {
    if (reduced.matches || !fine.matches || event.pointerType === 'touch') return;
    scenePointer = { x: event.clientX, y: event.clientY };
    if (!sceneFrame) sceneFrame = requestAnimationFrame(updateScene);
  }
  function motionPreferenceChanged() {
    if (reduced.matches) {
      if (observer) observer.disconnect();
      observer = null;
      Array.from(active).forEach(function (animation) { animation.cancel(); });
      clearSurface();
      clearScene();
      header.style.removeProperty('--orbit-scroll');
    } else {
      observeEntries();
      scheduleScroll();
    }
  }

  root.classList.add('orbit-motion-ready');
  observeEntries();
  scheduleScroll();
  window.addEventListener('scroll', scheduleScroll, { passive: true });
  window.addEventListener('resize', scheduleScroll, { passive: true });
  page.addEventListener('pointermove', onSurfaceMove, { passive: true });
  page.addEventListener('pointerleave', clearSurface);
  if (scene) {
    scene.addEventListener('pointermove', onSceneMove, { passive: true });
    scene.addEventListener('pointerleave', clearScene);
  }
  page.querySelectorAll('.orbit-faq-list details').forEach(function (details) {
    details.addEventListener('toggle', function () {
      var answer = details.querySelector('p');
      if (details.open && answer) {
        play(answer, [
          { opacity: .45, transform: 'translate3d(0,-5px,0)' },
          { opacity: 1, transform: 'translate3d(0,0,0)' }
        ], { duration: 300, easing: 'cubic-bezier(.18,.75,.25,1)' });
      }
      scheduleScroll();
    });
  });
  if (reduced.addEventListener) reduced.addEventListener('change', motionPreferenceChanged);
  if (fine.addEventListener) fine.addEventListener('change', function () {
    if (!fine.matches) { clearSurface(); clearScene(); }
  });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      clearSurface(); clearScene();
      Array.from(active).forEach(function (animation) { animation.cancel(); });
    } else scheduleScroll();
  });
}());
