// ui-enhance.js
// Non-invasive script that injects the UI CSS and provides an easy way to set red hover on elements
(function(){
  // Nothing to do if CSS already injected
  if (document.querySelector('link[href$="ui-enhance.css"]')) return;

  // create link to the CSS (this file is placed next to HTML files in the project root)
  var link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'ui-enhance.css';
  document.head.appendChild(link);

  // helper: convert elements with attribute data-hover="red" to class hover-red (works even if HTML authored differently)
  function markRedHover() {
    var els = document.querySelectorAll('[data-hover="red"]');
    for (var i=0;i<els.length;i++){
      els[i].classList.add('hover-red');
    }
  }

  // run on DOMContentLoaded and also in case pages dynamically render later
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markRedHover);
  } else { markRedHover(); }

  // Accessibility: ensure high contrast for small text inside buttons
  var tiny = document.querySelectorAll('button small, .btn small, .button small');
  for (var i=0;i<tiny.length;i++) tiny[i].style.color = '#dfeeff';
})();