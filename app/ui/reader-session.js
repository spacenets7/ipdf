(() => {
  const id=document.body.dataset.documentId;if(!id)return;
  let owner=false,last=null;
  fetch(`/api/papers/${id}/position`).then(async response=>{
    if(!response.ok)return;owner=true;const position=await response.json();
    if(position.section_id)document.dispatchEvent(new CustomEvent('ipdf:resume',{detail:position}));
  }).catch(()=>{});
  document.addEventListener('ipdf:position',event=>{if(!owner)return;last=event.detail;});
  function save(){if(owner&&last)fetch(`/api/papers/${id}/position`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(last),keepalive:true}).catch(()=>{});}
  setInterval(save,15000);window.addEventListener('pagehide',save);
})();
