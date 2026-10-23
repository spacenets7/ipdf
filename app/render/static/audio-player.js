/* Playback consumes pre-generated iPDF narration. It never calls an LLM. */
(() => {
  'use strict';
  const {paper,notify,safeUrl,sourceUrl}=window.ipdfViewer;
  const $=selector=>document.querySelector(selector);
  const ordered=paper.sections.map(s=>paper.narration.find(n=>n.section_id===s.id)).filter(Boolean);
  const audio=$('#narration-audio');
  const synth=window.speechSynthesis;
  let index=0,playing=false,paused=false,browser=false,simpler=false,epoch=0,utterance=null,speechParts=[],partIndex=0;
  const speed=()=>Number($('#playback-speed').value);
  const current=()=>ordered[index];
  function state(label) {
    $('#player-state').textContent=label;
    $('#toggle-play').textContent=playing?'Ⅱ':'▷';$('#toggle-play').setAttribute('aria-label',playing?'Pause narration':'Play narration');
    $('#walk-play').textContent=playing?'Ⅱ':'▷';$('#walk-play').setAttribute('aria-label',playing?'Pause narration':'Play narration');
    $('#play-paper').lastChild.textContent=playing?' Pause narration':' Listen to paper';
    if('mediaSession' in navigator) navigator.mediaSession.playbackState=playing?'playing':'paused';
  }
  function selected() {
    const segment=current();if(!segment)return;
    const section=paper.sections.find(s=>s.id===segment.section_id);
    $('#player-section-title').textContent=section.title;
    $('#walking-title').textContent=section.title;
    $('#walking-page').textContent=`PAGE ${segment.page} / ${paper.meta.pages}`;
    $('#walking-subtitle').textContent=simpler?'A simpler way into this section.':paper.meta.title;
    $('#walking-source').href=sourceUrl(segment.page);
    document.querySelectorAll('.paper-section').forEach(el=>el.classList.toggle('narrating',el.id===segment.section_id));
    document.getElementById(segment.section_id)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
    if('mediaSession' in navigator && 'MediaMetadata' in window) navigator.mediaSession.metadata=new MediaMetadata({title:section.title,artist:paper.meta.authors.slice(0,2).join(', '),album:paper.meta.title});
  }
  function stop() {
    epoch++;audio.pause();audio.removeAttribute('src');audio.load();
    if(synth)synth.cancel();utterance=null;playing=false;paused=false;
  }
  function complete(token) {
    if(token!==epoch)return;
    playing=false;paused=false;
    if(simpler){simpler=false;state('SIMPLER REPLAY FINISHED');return;}
    if(index+1<ordered.length){index++;start(false);}
    else {state('PAPER FINISHED · STAY CURIOUS');notify('End of the paper. Let the ideas settle.');}
  }
  function speakPart(token) {
    if(token!==epoch || !playing)return;
    if(partIndex>=speechParts.length){complete(token);return;}
    utterance=new SpeechSynthesisUtterance(speechParts[partIndex]);
    const voices=synth.getVoices();const voice=voices.find(v=>v.lang.startsWith('en')&&v.localService)||voices.find(v=>v.lang.startsWith('en'));
    if(voice)utterance.voice=voice;
    utterance.lang='en-US';utterance.rate=speed();
    utterance.onend=()=>{if(token===epoch){partIndex++;speakPart(token);}};
    utterance.onerror=event=>{if(token===epoch&&!['canceled','interrupted'].includes(event.error)){playing=false;state('VOICE PAUSED');notify('Your browser voice stopped. Tap play to resume this section.');}};
    synth.speak(utterance);
  }
  function browserPlay(script,token) {
    if(!synth || !('SpeechSynthesisUtterance' in window)){playing=false;state('BROWSER SPEECH UNAVAILABLE');notify('This browser has no speech voice. Try another browser or configure ElevenLabs on the server.');return;}
    browser=true;playing=true;paused=false;
    // Small utterances avoid long-text stalls in mobile browser speech engines.
    const sentences=script.match(/[^.!?]+[.!?]+|[^.!?]+$/g)||[script];
    speechParts=sentences.flatMap(s=>s.length>240 ? (s.match(/[\s\S]{1,220}(?:\s|$)/g)||[s]) : [s]);partIndex=0;
    state(simpler?'SIMPLER REPLAY · BROWSER VOICE':'PLAYING · BROWSER VOICE');speakPart(token);
  }
  async function hostedPlay(url,token) {
    const safe=safeUrl(url,'audio');if(!safe){browserPlay(simpler?current().simpler_script:current().script,token);return;}
    browser=false;audio.src=safe;audio.playbackRate=speed();
    try{await audio.play();if(token!==epoch){audio.pause();return;}playing=true;paused=false;state(simpler?'SIMPLER REPLAY · AUDIO':'PLAYING · AUDIO');}
    catch{playing=false;paused=true;state('AUDIO READY · TAP PLAY');notify('Audio is ready. Tap play to listen.');}
  }
  async function prepareHosted(segment,token) {
    const id=document.body.dataset.documentId;
    state('PREPARING AUDIO…');playing=false;
    try {
      const response=await fetch(`/audio/${encodeURIComponent(id)}/${encodeURIComponent(segment.section_id)}?simpler=${simpler?'true':'false'}`,{method:'POST'});
      const payload=await response.json();if(!response.ok)throw new Error(payload.detail||'Audio request failed');
      let result=payload;
      while(result.job_id || result.state==='queued' || result.state==='running') {
        const job=result.job_id||payload.job_id;
        await new Promise(resolve=>setTimeout(resolve,900));if(token!==epoch)return;
        const statusResponse=await fetch(`/ipdf/status/${encodeURIComponent(job)}`);
        const status=await statusResponse.json();
        if(!statusResponse.ok || status.state==='error')throw new Error('Hosted speech failed');
        if(status.state==='ready'){result=status.result;break;}
      }
      if(token!==epoch)return;
      if(result.provider==='elevenlabs'&&result.audio_url){segment[simpler?'simpler_audio_url':'audio_url']=result.audio_url;await hostedPlay(result.audio_url,token);}
      else {notify(result.message||'Using your browser voice.');browserPlay(simpler?segment.simpler_script:segment.script,token);}
    }catch{if(token===epoch){notify('Hosted audio is unavailable. Using your browser voice.');browserPlay(simpler?segment.simpler_script:segment.script,token);}}
  }
  let pendingOffset=0;
  document.addEventListener('ipdf:resume',event=>{if(playing)return;const found=ordered.findIndex(n=>n.section_id===event.detail.section_id);if(found>=0){index=found;pendingOffset=event.detail.offset||0;$('#playback-speed').value=String(event.detail.speed);}});
  audio.addEventListener('loadedmetadata',()=>{if(pendingOffset&&Number.isFinite(audio.duration)){audio.currentTime=Math.min(pendingOffset,audio.duration);pendingOffset=0;}});
  const resumeKey=`ipdf-resume:${paper.meta.paper_id}:${paper.meta.level}`;
  try {const saved=JSON.parse(localStorage.getItem(resumeKey)||'null');if(saved){const found=ordered.findIndex(n=>n.section_id===saved.section);if(found>=0)index=found;if([.75,1,1.25,1.5].includes(saved.speed))$('#playback-speed').value=String(saved.speed);}}catch{}
  function savePosition(){const position={section_id:current()?.section_id,speed:speed(),offset:browser?0:(audio.currentTime||0)};try{localStorage.setItem(resumeKey,JSON.stringify({section:position.section_id,speed:position.speed}));}catch{}if(position.section_id)document.dispatchEvent(new CustomEvent('ipdf:position',{detail:position}));}
  setInterval(savePosition,10000);
  function start(useSimpler=false) {
    useSimpler=useSimpler || Boolean(window.ipdfViewer.learning?.simpler && current()?.simpler_script);
    if(!ordered.length){notify('This edition has no generated narration yet. Source pages are still available to read.');return;}
    if(useSimpler&&!current().simpler_script){notify('This edition does not include a simpler replay for this section.');return;}
    stop();simpler=useSimpler;const token=epoch;selected();savePosition();
    const segment=current();const existing=useSimpler?segment.simpler_audio_url:segment.audio_url;
    if(existing)hostedPlay(existing,token);
    else if(paper.meta.tts_provider==='elevenlabs'&&document.body.dataset.documentId)prepareHosted(segment,token);
    else browserPlay(useSimpler?segment.simpler_script:segment.script,token);
  }
  function toggle() {
    if(!ordered.length){start();return;}
    if(playing){playing=false;paused=true;if(browser)synth.pause();else audio.pause();state('PAUSED · TAKE YOUR TIME');return;}
    if(paused){
      playing=true;paused=false;
      if(browser&&synth.paused){synth.resume();state('PLAYING · BROWSER VOICE');}
      else if(!browser&&audio.src){audio.play().then(()=>state('PLAYING · AUDIO')).catch(()=>{playing=false;paused=true;notify('Tap play again to allow audio.');});}
      else start(simpler);
    }else start(false);
  }
  function move(delta){if(!ordered.length)return;index=Math.max(0,Math.min(ordered.length-1,index+delta));start(false);}
  for(const selector of ['#toggle-play','#play-paper','#walk-play'])$(selector).addEventListener('click',toggle);
  for(const selector of ['#previous-section','#walk-prev'])$(selector).addEventListener('click',()=>move(-1));
  for(const selector of ['#next-section','#walk-next'])$(selector).addEventListener('click',()=>move(1));
  for(const selector of ['#walking-button','#dock-walking'])$(selector).addEventListener('click',()=>{if(!$('#walking-mode').open)$('#walking-mode').showModal();if(current())selected();});
  $('#explain-simpler').addEventListener('click',()=>start(true));
  $('#playback-speed').addEventListener('change',()=>{audio.playbackRate=speed();if(browser&&playing)start(simpler);});
  document.addEventListener('ipdf:play-section',event=>{const found=ordered.findIndex(n=>n.section_id===event.detail.section_id);if(found>=0){index=found;start(false);}});
  audio.addEventListener('ended',()=>complete(epoch));
  audio.addEventListener('error',()=>{if(!browser&&audio.src&&current()){notify('The audio track failed. Switching to browser speech.');browserPlay(simpler?current().simpler_script:current().script,epoch);}});
  if('mediaSession' in navigator){
    const actions={play:()=>{if(!playing)toggle();},pause:()=>{if(playing)toggle();},previoustrack:()=>move(-1),nexttrack:()=>move(1),
      seekbackward:()=>{if(!browser)audio.currentTime=Math.max(0,audio.currentTime-15);},seekforward:()=>{if(!browser&&Number.isFinite(audio.duration))audio.currentTime=Math.min(audio.duration,audio.currentTime+15);}};
    Object.entries(actions).forEach(([action,handler])=>{try{navigator.mediaSession.setActionHandler(action,handler);}catch{}});
  }
  if(!ordered.length){$('#listening-note').textContent='No narration in this edition. All extracted source pages remain readable.';state('SOURCE-ONLY EDITION');}
  window.addEventListener('pagehide',()=>{savePosition();if(synth)synth.cancel();});
})();
