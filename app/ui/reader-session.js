(() => {
  const id=document.body.dataset.documentId;if(!id)return;
  let owner=false,last=null;
  const ask=document.querySelector('#ask-current-section');
  function setAsk(section){if(ask&&section)ask.href=`/tutor/${id}?section=${encodeURIComponent(section)}`;}
  setAsk(window.ipdfViewer?.paper.sections[0]?.id);
  fetch(`/api/papers/${id}/position`).then(async response=>{
    if(!response.ok)return;owner=true;const position=await response.json();
    if(position.section_id){setAsk(position.section_id);document.dispatchEvent(new CustomEvent('ipdf:resume',{detail:position}));}
  }).catch(()=>{});
  document.addEventListener('ipdf:position',event=>{if(!owner)return;last=event.detail;setAsk(last.section_id);});
  function save(){if(owner&&last)fetch(`/api/papers/${id}/position`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(last),keepalive:true}).catch(()=>{});}
  setInterval(save,15000);window.addEventListener('pagehide',save);
})();
