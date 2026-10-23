'use strict';
document.querySelector('#open').addEventListener('click', async () => {
  const status=document.querySelector('#status');
  try {
    const file=document.querySelector('#paper').files[0];
    if(!file)throw new Error('Choose an .ipdf.json file first.');
    if(file.size>40*1024*1024)throw new Error('Please use a JSON file smaller than 40 MB.');
    const paper=JSON.parse(await file.text());
    if(paper.ipdf_version!=='0.1'||!paper.meta||!Array.isArray(paper.sections)||!paper.sections.length||!paper.provenance)throw new Error('This file is not an iPDF 0.1 document.');
    for(const key of ['glossary','flashcards','charts','narration','figures','tables','issues']) {
      paper[key]??=[];
      if(!Array.isArray(paper[key]))throw new Error(`Invalid ${key} collection.`);
    }
    paper.meta.authors??=[];
    paper.meta.pages??=Math.max(...paper.sections.map(s=>s.page));
    paper.meta.paper_id??=file.name;
    paper.meta.tts_provider='browser';
    paper.provenance.prompt_tokens??=0;
    paper.provenance.completion_tokens??=0;
    paper.provenance.recorded_cost_usd??=0;
    paper.provenance.prompt_versions??={};
    const response=await fetch('viewer-template.html');
    if(!response.ok)throw new Error('The reader could not load. Please retry.');
    const template=await response.text();
    const payload=JSON.stringify(paper).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
    const html=template.replace('__IPDF_PAYLOAD__',()=>payload);
    const frame=document.createElement('iframe');
    frame.title=paper.meta.title || 'iPDF reader';
    frame.style.cssText='width:100%;height:calc(100dvh - 48px);border:0;display:block';
    const exportUrl=URL.createObjectURL(new Blob([html],{type:'text/html'}));
    frame.srcdoc=html.replace("$('#download-html').href=location.href;",()=>"$('#download-html').href="+JSON.stringify(exportUrl)+';');
    const back=document.createElement('a');
    back.href='./';back.textContent='← Open another paper';
    back.style.cssText='display:block;padding:12px 20px;height:48px';
    document.body.replaceChildren(back,frame);
  } catch(error) {status.textContent=error.message;}
});
