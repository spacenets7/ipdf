(() => {
  'use strict';
  const $=selector=>document.querySelector(selector);
  const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(cls)node.className=cls;return node;};
  const link=(text,url,cls='button secondary')=>{const a=make('a',text,cls);a.href=url;return a;};
  let library=[],lastPapers='',lastJobs='';
  function renderPapers(){
    const papers=$('#papers'),query=$('#paper-search').value.trim().toLocaleLowerCase();papers.replaceChildren();
    const visible=library.filter(p=>p.title.toLocaleLowerCase().includes(query));
    if(!visible.length){const empty=make('div',null,'empty-state');empty.append(make('span',query?'⌕':'▤','empty-icon'),make('h3',query?'No matching papers':'Make room for your next idea.'),make('p',query?'Try another title.':'Upload a research paper. Come back to a new way to read, learn and listen.'));if(!query)empty.append(link('＋ Add your first paper','/#create-form','button primary'));papers.append(empty);return;}
    visible.forEach(p=>{
      const card=make('article',null,'library-card'),top=make('div',null,'paper-card-top');
      top.append(make('span','▤','paper-file-icon'),make('span',p.public?'Shared by link':'Private','state-badge'));
      const title=make('h3');title.append(link(p.title,`/ipdf/${p.id}`,'paper-title-link'));
      const meta=make('div',null,'paper-card-meta');meta.append(make('span',p.level,'level-badge'),make('span',`${p.narration} audio section${p.narration===1?'':'s'}`));
      const tools=make('p',null,'paper-tools');tools.append(make('span','Glossary'),make('span','Study cards'),make('span','Tutor'));
      card.append(top,title,meta,tools);
      const actions=make('div',null,'actions paper-card-actions');actions.append(link('Read paper ↗',`/ipdf/${p.id}`,'button primary'),link('Learn & ask',`/tutor/${p.id}`));card.append(actions);
      const footer=make('div',null,'paper-card-footer');footer.append(link('Export ↓',`/ipdf/${p.id}/export`,'small-link'));
      const share=make('button',p.public?'Make private':'Share by link','text-button');share.addEventListener('click',async()=>{share.disabled=true;try{const r=await fetch(`/api/papers/${p.id}/sharing`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({public:!p.public})});if(!r.ok)throw Error('Sharing could not be updated. Try again.');await load();}catch(error){showError(error.message);}finally{share.disabled=false;}});footer.append(share);
      if(p.notes.length){const notes=make('details',null,'paper-notes');notes.append(make('summary',`${p.notes.length} edition note${p.notes.length===1?'':'s'}`));p.notes.forEach(note=>notes.append(make('p',typeof note==='string'?note:JSON.stringify(note))));footer.append(notes);}card.append(footer);papers.append(card);
    });
  }
  function showError(message){$('#library-error').textContent=message;$('#library-error').hidden=false;}
  function jobRow(j){
    const row=make('div',null,'job-row'),info=make('div',null,'job-info');info.append(make('strong',j.label||({prepare:'Learning path',tutor:'Paper tutor',audio:'Narration'}[j.kind]||'Paper edition')),make('span',j.message||'Queued'));
    const state=make('span',j.state,'state-badge');state.dataset.state=j.state;row.append(info,state);
    if(j.state==='queued'||j.state==='running'){const progress=make('progress');progress.max=100;progress.value=j.progress;progress.setAttribute('aria-label',`${j.label||j.kind} progress`);row.append(progress);}
    if(j.error)row.append(make('p',j.error,'job-error'));
    if(j.state==='error'){const retry=make('button','Retry ↻','small-button');retry.addEventListener('click',async()=>{retry.disabled=true;try{const r=await fetch(`/api/jobs/${j.id}/retry`,{method:'POST'});if(!r.ok)throw Error('This job could not be retried.');await load();}catch(error){showError(error.message);}finally{retry.disabled=false;}});row.append(retry);}return row;
  }
  async function load(){try{
    const response=await fetch('/api/library');if(!response.ok)throw Error('Sign in again to open your library.');const data=await response.json();
    const paperSignature=JSON.stringify(data.papers);if(paperSignature!==lastPapers){library=data.papers;renderPapers();lastPapers=paperSignature;}$('#library-error').hidden=true;
    const active=data.jobs.filter(j=>j.state==='queued'||j.state==='running'),pending=data.jobs.filter(j=>j.state!=='ready'),completed=data.jobs.filter(j=>j.state==='ready');
    $('#paper-count').textContent=library.length;$('#active-count').textContent=active.length;$('#library-total').textContent=library.length;
    $('#queue-summary').textContent=active.length?`${active.length} preparing`:'Up to date';$('#queue-summary').dataset.state=active.length?'running':'ready';
    const jobSignature=JSON.stringify(data.jobs);if(jobSignature===lastJobs)return;lastJobs=jobSignature;
    const queue=$('#queue'),wasOpen=Boolean(queue.querySelector('details')?.open);queue.replaceChildren();
    if(!pending.length)queue.append(make('p',completed.length?'All caught up. Your tools are ready.':'Nothing preparing. Add a paper to get started.','queue-empty'));
    pending.slice(0,20).forEach(j=>queue.append(jobRow(j)));
    if(completed.length){const history=make('details',null,'queue-history');history.open=wasOpen;history.append(make('summary',`Completed jobs · ${completed.length}`));completed.slice(0,20).forEach(j=>history.append(jobRow(j)));queue.append(history);}
  }catch(error){showError(error.message);}}
  $('#paper-search').addEventListener('input',renderPapers);load();setInterval(load,8000);
})();
