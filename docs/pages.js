'use strict';
const previewTerm=document.querySelector('#preview-term');
previewTerm.addEventListener('click',()=>{
  const expanded=previewTerm.getAttribute('aria-expanded')==='true';
  previewTerm.setAttribute('aria-expanded',String(!expanded));
  document.querySelector('#preview-definition').hidden=expanded;
});
