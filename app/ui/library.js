(() => {
  const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text)node.textContent=text;if(cls)node.className=cls;return node;};
  const link=(text,url)=>{const a=make('a',text,'button secondary');a.href=url;return a;};
  async function load(){try{
    const response=await fetch('/api/library');if(!response.ok)throw Error('Sign in again to open your library.');
    const data=await response.json();const papers=document.querySelector('#papers'),queue=document.querySelector('#queue');papers.replaceChildren();queue.replaceChildren();
    if(!data.papers.length)papers.append(make('p','Your first paper will appear here. Upload a PDF to get started.'));
    data.papers.forEach(p=>{const card=make('article',null,'library-card');card.append(make('span',p.public?'Shared by link':'Private','state-badge'),make('h3',p.title),make('p',`${p.level} · ${p.narration} narration segments · ${p.notes.length} edition notes`));
      const actions=make('div',null,'actions');actions.append(link('Read',`/ipdf/${p.id}`),link('Learn & ask',`/tutor/${p.id}`),link('Export',`/ipdf/${p.id}/export`));
      const share=make('button',p.public?'Make private':'Share by link','small-button');share.addEventListener('click',async()=>{const r=await fetch(`/api/papers/${p.id}/sharing`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({public:!p.public})});if(r.ok)load();});actions.append(share);card.append(actions);papers.append(card);});
    if(!data.jobs.length)queue.append(make('p','No papers preparing. You can close the tab after uploading; check progress here later.'));
    data.jobs.slice(0,20).forEach(j=>{const row=make('div',null,'job-row');row.append(make('span',`${j.label||j.kind} · ${j.message} · ${j.progress}%`),make('span',j.state,'state-badge'));
      if(j.error)row.append(make('p',j.error));
      if(j.state==='error'){const retry=make('button','Retry','small-button');retry.addEventListener('click',async()=>{await fetch(`/api/jobs/${j.id}/retry`,{method:'POST'});load();});row.append(retry);}queue.append(row);});
  }catch(error){document.querySelector('#library-error').textContent=error.message;}}
  load();setInterval(load,8000);
})();
