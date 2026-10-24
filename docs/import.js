'use strict';
const input=document.querySelector('#paper'),drop=document.querySelector('#file-drop'),openButton=document.querySelector('#open'),status=document.querySelector('#status');
let selectedFile=null;
function selectFile(file){selectedFile=file||null;document.querySelector('#selected-file').textContent=selectedFile?selectedFile.name:'.ipdf.json · up to 40 MB';status.textContent='';}
input.addEventListener('change',()=>selectFile(input.files[0]));
for(const event of ['dragenter','dragover'])drop.addEventListener(event,e=>{e.preventDefault();drop.classList.add('is-dragging');});
for(const event of ['dragleave','drop'])drop.addEventListener(event,e=>{e.preventDefault();drop.classList.remove('is-dragging');});
drop.addEventListener('drop',event=>selectFile(event.dataTransfer.files[0]));
openButton.addEventListener('click',async()=>{
  openButton.disabled=true;status.textContent='Opening your edition…';
  try{
    const file=selectedFile||input.files[0];
    if(!file)throw Error('Choose an .ipdf.json file first.');
    if(file.size>40*1024*1024)throw Error('Please use a JSON file smaller than 40 MB.');
    const paper=JSON.parse(await file.text());
    if(paper?.ipdf_version!=='0.1'||!paper.meta||typeof paper.meta.title!=='string'||!Array.isArray(paper.sections)||!paper.sections.length||!paper.provenance)throw Error('This file is not an iPDF 0.1 document.');
    for(const section of paper.sections){if(!section||typeof section.id!=='string'||typeof section.title!=='string'||typeof section.text!=='string'||!Number.isInteger(section.page)||section.page<1)throw Error('The document has an invalid section. Export it again from the app.');}
    for(const key of ['glossary','flashcards','charts','narration','figures','tables','issues']){paper[key]??=[];if(!Array.isArray(paper[key]))throw Error(`Invalid ${key} collection.`);}
    paper.meta.authors??=[];if(!Array.isArray(paper.meta.authors)||paper.meta.authors.some(author=>typeof author!=='string'))throw Error('Invalid author information.');
    paper.meta.pages??=paper.sections.reduce((max,s)=>Math.max(max,s.page),1);
    paper.meta.paper_id??=file.name;paper.meta.tts_provider='browser';
    paper.provenance.prompt_tokens??=0;paper.provenance.completion_tokens??=0;paper.provenance.recorded_cost_usd??=0;paper.provenance.prompt_versions??={};
    const response=await fetch('viewer-template.html');if(!response.ok)throw Error('The reader could not load. Please retry.');
    const template=await response.text(),payload=JSON.stringify(paper).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
    const html=template.replace('__IPDF_PAYLOAD__',()=>payload),frame=document.createElement('iframe');
    frame.title=paper.meta.title||'iPDF reader';frame.className='import-reader';
    const exportUrl=URL.createObjectURL(new Blob([html],{type:'text/html'}));
    frame.srcdoc=html.replace("$('#download-html').href=location.href;",()=>"$('#download-html').href="+JSON.stringify(exportUrl)+';');
    const bar=document.createElement('header');bar.className='import-reader-bar';
    const back=document.createElement('a');back.href='./';back.textContent='← Open another paper';
    const title=document.createElement('strong');title.textContent=paper.meta.title;bar.append(back,title);
    document.body.classList.add('reader-open');document.body.replaceChildren(bar,frame);document.title=paper.meta.title+' — iPDF';
    window.addEventListener('pagehide',()=>URL.revokeObjectURL(exportUrl),{once:true});
  }catch(error){status.textContent=error instanceof SyntaxError?'That file is not valid JSON. Choose an exported .ipdf.json edition.':error.message;}
  finally{openButton.disabled=false;}
});
