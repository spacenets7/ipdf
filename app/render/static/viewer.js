/* Renderer: reads only iPDF JSON. No model or generation requests. */
(() => {
  'use strict';
  const paper = JSON.parse(document.querySelector('#ipdf-data').textContent);
  if (paper.ipdf_version !== '0.1') throw new Error('Unsupported iPDF version');
  const $ = selector => document.querySelector(selector);
  const el = (tag, className, text) => { const node=document.createElement(tag); if(className) node.className=className; if(text!==undefined) node.textContent=text; return node; };
  let toastTimer;
  const notify = message => { $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>{$('#toast').hidden=true;},5500); };
  const safeUrl = (value, type='link') => {
    if (!value) return '';
    if (type === 'image' && /^data:image\/(png|jpeg|webp);base64,/i.test(value)) return value;
    if (type === 'audio' && /^data:audio\/mpeg;base64,/i.test(value)) return value;
    try { const url = new URL(value, location.href); if (['http:','https:','blob:'].includes(url.protocol)) return url.href; } catch {}
    return '';
  };
  let pdfUrl=safeUrl(paper.meta.source_url);
  if (/^data:application\/pdf;base64,/.test(paper.assets?.original_pdf || '')) {
    const binary=atob(paper.assets.original_pdf.split(',')[1]);
    pdfUrl=URL.createObjectURL(new Blob([Uint8Array.from(binary,char=>char.charCodeAt(0))],{type:'application/pdf'}));
  }
  const sourceUrl = page => pdfUrl ? `${pdfUrl.split('#')[0]}#page=${page}` : '';
  const sourceLink = (page, text='View original ↗') => { const link=el('a','source-link',text); link.href=sourceUrl(page); link.target='_blank'; link.rel='noopener'; return link; };
  $('#paper-title').textContent=paper.meta.title;
  $('#paper-authors').textContent=paper.meta.authors.join(' · ') || 'Research paper';
  $('#level-badge').textContent=paper.meta.level;
  $('#page-count').textContent=`${paper.meta.pages} pages`;
  $('#original-link').href=sourceUrl(1);
  if(paper.issues.length) {
    const details=el('details','edition-notice');
    const summary=el('summary','',`${paper.issues.length} note${paper.issues.length===1?'':'s'} about this edition`);
    details.append(summary);
    paper.issues.forEach(issue=>details.append(el('p','',`${issue.page ? `Page ${issue.page} · `:''}${issue.message}`)));
    $('#document-notices').append(details);
  }
  const deckKey=`ipdf-deck:${paper.meta.paper_id}:${paper.meta.level}`;
  let deck=[];
  try { deck=JSON.parse(localStorage.getItem(deckKey)||'[]'); if(!Array.isArray(deck)) deck=[]; } catch {}
  function save(card) {
    if(!deck.some(entry=>entry.id===card.id)) deck.push(card);
    try {localStorage.setItem(deckKey,JSON.stringify(deck));} catch {notify('Browser storage is unavailable. This deck is saved for the current session.');}
    $('#deck-count').textContent=deck.length; notify('A good idea, saved to your deck.');
  }
  $('#deck-count').textContent=deck.length;
  let activeCard;
  let hoverClose;
  function showTerm(entry,modal=true,anchor=null) {
    const dialog=$('#term-popover');
    clearTimeout(hoverClose);
    if(dialog.open && modal && !dialog.matches(':modal'))dialog.close();
    if(modal){dialog.style.margin='';dialog.style.left='';dialog.style.top='';}
    $('#term-title').textContent=entry.term;
    $('#term-definition').textContent=entry.definition;
    $('#term-provenance').textContent=`Page ${entry.page} · ${entry.generated_by.model} · ${entry.generated_by.prompt_version}`;
    $('#term-source').href=sourceUrl(entry.page);
    activeCard={id:`term:${entry.section_id}:${entry.term}`,front:entry.term,back:entry.definition,page:entry.page};
    $('#save-term').textContent=deck.some(card=>card.id===activeCard.id)?'Saved to deck ✓':'Save to deck +';
    if(!dialog.open){if(modal)dialog.showModal();else dialog.show();}
    if(!modal&&anchor){const box=anchor.getBoundingClientRect();dialog.style.margin='0';dialog.style.left=`${Math.max(15,Math.min(innerWidth-dialog.offsetWidth-15,box.left))}px`;dialog.style.top=`${Math.max(80,Math.min(innerHeight-dialog.offsetHeight-20,box.bottom+10))}px`;}
  }
  $('#term-popover').addEventListener('mouseenter',()=>clearTimeout(hoverClose));
  $('#term-popover').addEventListener('mouseleave',()=>{if(!$('#term-popover').matches(':modal'))$('#term-popover').close();});
  $('#save-term').addEventListener('click',()=>{save(activeCard);$('#save-term').textContent='Saved to deck ✓';});
  const escapeRegex = value => value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  function annotatedText(text, terms) {
    const fragment=document.createDocumentFragment();
    if(!terms.length) {fragment.append(document.createTextNode(text));return fragment;}
    const pattern=new RegExp(`(${terms.map(term=>escapeRegex(term.term)).sort((a,b)=>b.length-a.length).join('|')})`,'gi');
    let start=0;
    for(const match of text.matchAll(pattern)) {
      fragment.append(document.createTextNode(text.slice(start,match.index)));
      const entry=terms.find(term=>term.term.toLowerCase()===match[0].toLowerCase());
      const button=el('button','glossary-term',match[0]); button.type='button';button.title=entry.definition;button.setAttribute('aria-label',`Explain ${match[0]}`);
      button.addEventListener('click',()=>showTerm(entry));
      button.addEventListener('mouseenter',()=>{if(matchMedia('(hover: hover) and (pointer: fine)').matches)showTerm(entry,false,button);});
      button.addEventListener('mouseleave',()=>{hoverClose=setTimeout(()=>{const dialog=$('#term-popover');if(dialog.open&&!dialog.matches(':modal')&&!dialog.matches(':hover'))dialog.close();},250);});
      fragment.append(button); start=match.index+match[0].length;
    }
    fragment.append(document.createTextNode(text.slice(start))); return fragment;
  }
  for(const [index,section] of paper.sections.entries()) {
    const article=el('section','paper-section');article.id=section.id;article.dataset.page=section.page;
    const heading=el('div','section-heading');
    const label=el('span','page-label',`PAGE ${String(section.page).padStart(2,'0')}`);
    heading.append(label,sourceLink(section.page));article.append(heading,el('h2','',section.title));
    const terms=paper.glossary.filter(entry=>entry.section_id===section.id);
    const paragraphs=section.text.split(/\n\s*\n/).flatMap(paragraph=>{
      const parts=[];let rest=paragraph;
      while(rest.length>1500){let cut=rest.lastIndexOf(' ',1000);if(cut<1)cut=1000;parts.push(rest.slice(0,cut));rest=rest.slice(cut).trimStart();}
      if(rest)parts.push(rest);return parts;
    });
    for(const text of paragraphs) {const p=el('p','source-paragraph');p.append(annotatedText(text.replace(/\n/g,' '),terms));article.append(p);}
    const cards=paper.flashcards.filter(card=>card.section_id===section.id);
    if(cards.length) {
      const group=el('div','study-cards');group.append(el('div','eyebrow','A QUESTION TO KEEP'));
      for(const card of cards) {
        const details=el('details','study-card');details.append(el('summary','',card.front));
        const answer=el('div','card-answer');answer.append(el('p','',card.back));
        const actions=el('div','card-actions');const button=el('button','small-button','Save to deck +');
        button.addEventListener('click',()=>{save(card);button.textContent='Saved ✓';});actions.append(button,sourceLink(card.page));answer.append(actions);details.append(answer);group.append(details);
      }article.append(group);
    }
    for(const chart of paper.charts.filter(chart=>chart.page===section.page)) {
      const figure=el('figure','evidence-chart');figure.append(el('div','eyebrow','THE NUMBERS, IN VIEW'),el('h3','',chart.title));
      const container=el('div','chart-container');const canvas=el('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',chart.title);container.append(canvas);figure.append(container);
      const caption=el('figcaption');caption.append(sourceLink(chart.page,chart.caption));figure.append(caption);
      const table=el('table','chart-data');const head=el('tr');head.append(el('th','','Source label'),...chart.series.map(s=>el('th','',s.name)));table.append(head);
      chart.series[0].labels.forEach((label,i)=>{const row=el('tr');row.append(el('th','',label),...chart.series.map(s=>el('td','',String(s.values[i]??''))));table.append(row);});
      const evidence=el('details','chart-evidence');evidence.append(el('summary','','Inspect source values'),table);figure.append(evidence);article.append(figure);
      const horizontal=chart.type==='bar'&&chart.series[0].labels.some(label=>label.length>18);
      if(horizontal)container.style.height=`${Math.max(230,Math.min(700,chart.series[0].labels.length*29+45))}px`;
      const category={grid:{display:false},ticks:{font:{size:10},callback:function(value){const label=this.getLabelForValue(value);return label.length>22?label.slice(0,21)+'…':label;}}};
      const numeric={beginAtZero:true,grid:{color:'#e4e8dd'},ticks:{font:{size:10}}};
      if(window.Chart) new Chart(canvas,{type:chart.type,data:{labels:chart.series[0].labels,datasets:chart.series.map((s,i)=>({label:s.name,data:s.values,borderWidth:1.5,borderRadius:4,backgroundColor:['#517969bb','#c98668bb','#b6bc90bb','#899ab7bb','#d1b772bb'][i%5],borderColor:['#517969','#c98668','#9ca672','#899ab7','#b9a253'][i%5]}))},options:{indexAxis:horizontal?'y':'x',responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:chart.series.length>1,position:'bottom'}},scales:{x:horizontal?numeric:category,y:horizontal?category:numeric}}});
      else container.replaceWith(el('p','', 'Chart unavailable; inspect the source values below.'));
    }
    for(const figure of paper.figures.filter(figure=>figure.page===section.page)) {
      const url=safeUrl(figure.data_url,'image');if(!url)continue;
      const block=el('figure','paper-figure');const image=el('img');image.src=url;image.alt=figure.caption;image.loading='lazy';const caption=el('figcaption');caption.append(document.createTextNode(figure.caption+' '),sourceLink(figure.page));block.append(image,caption);article.append(block);
    }
    const segment=paper.narration.find(n=>n.section_id===section.id);
    if(segment) {const button=el('button','section-listen',`▷ Listen to page ${section.page}`);button.addEventListener('click',()=>document.dispatchEvent(new CustomEvent('ipdf:play-section',{detail:{section_id:section.id}})));article.append(button);}
    $('#sections').append(article);
    for(const target of ['#desktop-contents','#mobile-contents']) {
      const link=el('a','outline-link');link.href='#'+section.id;link.append(el('span','',String(section.page).padStart(2,'0')),el('span','',section.title));
      link.addEventListener('click',()=>$('#contents-dialog').close());$(target).append(link);
    }
  }
  const provenance=paper.provenance;
  $('#provenance').append(el('p','',`Generated with ${provenance.model} · ${new Date(provenance.generated_at).toLocaleDateString()}`),
    el('p','',`${provenance.prompt_tokens.toLocaleString()} input tokens · ${provenance.completion_tokens.toLocaleString()} output tokens`),
    el('p','',provenance.prices_configured ? `Recorded generation cost: $${provenance.recorded_cost_usd.toFixed(5)}` : 'Provider prices were not configured; recorded cost is not a billing estimate.'),
    el('p','',Object.values(provenance.prompt_versions).join(' · ')),
    el('p','', 'Generated learning blocks can contain errors. Every block links back to its source page.'));
  function showDeck() {
    $('#deck-cards').replaceChildren();
    if(!deck.length) $('#deck-cards').append(el('p','empty-deck','A term that clicks. A question that stays. Save your first card from the paper.'));
    for(const card of deck) {
      const details=el('details','study-card');details.append(el('summary','',card.front));const body=el('div','card-answer');body.append(el('p','',card.back));
      const actions=el('div','card-actions');actions.append(sourceLink(card.page));const remove=el('button','small-button','Remove');remove.addEventListener('click',()=>{deck=deck.filter(c=>c.id!==card.id);try{localStorage.setItem(deckKey,JSON.stringify(deck));}catch{}$('#deck-count').textContent=deck.length;showDeck();});actions.append(remove);body.append(actions);details.append(body);$('#deck-cards').append(details);
    }
    if(!$('#deck-dialog').open)$('#deck-dialog').showModal();
  }
  $('#deck-button').addEventListener('click',showDeck);
  $('#contents-button').addEventListener('click',()=>$('#contents-dialog').showModal());
  $('#export-menu-button').addEventListener('click',()=>$('#export-dialog').showModal());
  document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>document.getElementById(button.dataset.close).close()));
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',event=>{if(event.target===dialog){const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)dialog.close();}}));
  const id=document.body.dataset.documentId;
  if(id) {$('#download-html').href=`/ipdf/${id}/export`;$('#download-json').href=`/ipdf/${id}.json`;$('#download-json').download=`${id}.ipdf.json`;}
  else {
    $('#download-html').href=location.href;$('#download-html').download='paper.ipdf.html';
    $('#download-json').href=URL.createObjectURL(new Blob([JSON.stringify(paper,null,2)],{type:'application/json'}));$('#download-json').download='paper.ipdf.json';
  }
  const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){const page=Number(entry.target.dataset.page);$('#reading-progress-bar').style.width=`${page/paper.meta.pages*100}%`;document.querySelectorAll('.outline-link').forEach(link=>link.classList.toggle('current',link.getAttribute('href')==='#'+entry.target.id));}}},{rootMargin:'-15% 0px -60% 0px'});
  document.querySelectorAll('.paper-section').forEach(section=>observer.observe(section));
  window.ipdfViewer={paper,notify,safeUrl,sourceUrl};
})();
