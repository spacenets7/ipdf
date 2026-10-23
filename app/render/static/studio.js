(() => {
  'use strict';
  const form=document.querySelector('#create-form'),button=document.querySelector('#create-button'),error=document.querySelector('#create-error');
  form.querySelectorAll('[name=source]').forEach(input=>input.addEventListener('change',()=>{document.querySelector('#arxiv-field').hidden=input.value!=='arxiv';document.querySelector('#upload-field').hidden=input.value!=='upload';}));
  document.querySelector('#sample-paper').addEventListener('click',()=>document.querySelector('#arxiv-id').value='1706.03762');
  document.querySelector('#pdf-file').addEventListener('change',event=>{document.querySelector('#file-name').textContent=[...event.target.files].map(f=>f.name).join(', ')||'Up to 3 PDFs · 25 MB each';});
  form.addEventListener('submit',async event=>{
    event.preventDefault();error.hidden=true;const selected=form.querySelector('[name=source]:checked').value,files=[...document.querySelector('#pdf-file').files];
    if(selected==='upload'&&(!files.length||files.length>3||files.some(f=>f.size>25_000_000))){error.textContent='Choose up to three PDFs, each under 25 MB.';error.hidden=false;return;}
    const arxiv=document.querySelector('#arxiv-id').value.trim();if(selected==='arxiv'&&!arxiv){error.textContent='Enter an arXiv ID or choose PDFs.';error.hidden=false;return;}
    button.disabled=true;let accepted=0;
    try{
      const items=selected==='upload'?files:[null];
      for(const file of items){const body=new FormData();for(const key of ['background','goal','minutes','voice'])body.append(key,form.elements[key].value);body.append('level',form.querySelector('[name=level]:checked').value);if(file)body.append('pdf',file);else body.append('arxiv_id',arxiv);
        const response=await fetch('/ipdf/create',{method:'POST',body});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Could not queue this paper.');accepted++;
        document.querySelector('#job-progress').hidden=false;document.querySelector('#job-message').textContent=`${accepted} paper(s) queued. You can close this tab.`;
      }
      location.assign('/library');
    }catch(failure){error.textContent=`${accepted?accepted+' paper(s) already queued. ':''}${failure.message} Open your library to check them.`;error.hidden=false;button.disabled=false;}
  });
})();
