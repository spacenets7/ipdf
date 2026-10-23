(() => {
  'use strict';
  const id=document.body.dataset.documentId,$=s=>document.querySelector(s);
  const status=message=>$('#tutor-status').textContent=message;
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
  let lastAnswer=null,recognition=null,questionPending=false;
  const requested=new URLSearchParams(location.search).get('section');
  if([...$('#tutor-section').options].some(option=>option.value===requested))$('#tutor-section').value=requested;
  $('#return-paper').href=`/ipdf/${id}#${encodeURIComponent($('#tutor-section').value)}`;
  const audio=$('#answer-audio'),speech=window.speechSynthesis;
  function interrupt(){audio.pause();speech?.cancel();}
  function play(answer){
    if(!answer)return;interrupt();lastAnswer=answer;
    if(answer.audio?.audio_url){audio.src=answer.audio.audio_url;audio.play().catch(()=>status('Tap Replay to allow audio.'));}
    else if(speech){const utterance=new SpeechSynthesisUtterance(answer.text);utterance.lang='en-US';speech.speak(utterance);}
    else status('Speech is unavailable; your explanation is shown below.');
  }
  async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'The request could not finish.');return data;}
  async function poll(job){for(let count=0;count<300;count++){const r=await fetch('/ipdf/status/'+job);if(!r.ok)throw Error('Job unavailable. Check your library.');const result=await r.json();status(result.message);if(result.state==='ready')return result.result;if(result.state==='error')throw Error(result.error||'Job failed. Retry from the library.');await new Promise(resolve=>setTimeout(resolve,1500));}throw Error('Still preparing. Return to your library later.');}
  function turn(question,answer){const card=node('article',null,'turn');card.append(node('h3',question),node('p',answer.text));
    if(answer.source_quote)card.append(node('blockquote',answer.source_quote));
    const source=node('a',`Read source · page ${answer.page}`,'small-link');source.href=`/ipdf/${id}#${encodeURIComponent(answer.section_id)}`;card.append(source,node('p',`${answer.model} · ${answer.prompt_version}`));
    const replay=node('button','Listen to this answer','button secondary');replay.addEventListener('click',()=>play(answer));card.append(replay);$('#turns').append(card);lastAnswer=answer;
  }
  async function load(){const r=await fetch('/api/tutor/'+id);if(!r.ok)throw Error('Sign in to open your tutor.');const data=await r.json();$('#concepts').replaceChildren();
    if(!data.map){$('#concepts').append(node('p','Your learning path is preparing. Check the library queue or prepare it here.'));}
    else {const familiar=new Map(data.memory.map(m=>[m.concept,Boolean(m.familiar)])),lookup=new Map(data.map.concepts.map(c=>[c.name,c])),ordered=[],visited=new Set();
      function visit(c){if(visited.has(c.name))return;visited.add(c.name);c.depends_on.forEach(name=>{if(lookup.has(name))visit(lookup.get(name));});ordered.push(c);}data.map.concepts.forEach(visit);
      ordered.forEach(c=>{const card=node('article',null,'concept-card');card.append(node('span',familiar.get(c.name)?'Familiar':'To explore','state-badge'),node('h3',c.name),node('p',c.explanation),node('p','Builds on: '+(c.depends_on.join(', ')||'Start here')),node('blockquote',c.source_quote));
        const source=node('a',`Source page ${c.page}`,'small-link');source.href=`/ipdf/${id}#${encodeURIComponent(c.section_id)}`;card.append(source);
        const actions=node('div',null,'actions');const know=node('button',familiar.get(c.name)?'Revisit this':'I know this','button secondary');know.addEventListener('click',async()=>{await api(`/api/tutor/${id}/memory`,{concept:c.name,familiar:!familiar.get(c.name)});await load();});
        const explain=node('button','Explain this first','button primary');explain.addEventListener('click',()=>{$('#tutor-section').value=c.section_id;$('#question').value=`Explain ${c.name} and the prerequisite ideas I need, using this section.`;$('#question').focus();$('#conversation').scrollIntoView({behavior:'smooth'});});actions.append(know,explain);card.append(actions);$('#concepts').append(card);});}
    $('#turns').replaceChildren();data.turns.forEach(t=>turn(t.question,t.answer));
  }
  $('#prepare-path').addEventListener('click',async()=>{try{const r=await api(`/api/tutor/${id}/prepare`);await poll(r.job_id);await load();}catch(e){status(e.message);}});
  $('#question-form').addEventListener('submit',async event=>{event.preventDefault();if(questionPending)return;interrupt();questionPending=true;$('#ask-button').disabled=true;const question=$('#question').value;
    try{const r=await api(`/api/tutor/${id}/ask`,{section_id:$('#tutor-section').value,question});const answer=await poll(r.job_id);turn(question,answer);play(answer);status('Explanation ready. Continue your paper whenever you like.');}
    catch(error){status(error.message);}finally{questionPending=false;$('#ask-button').disabled=false;}});
  $('#replay-answer').addEventListener('click',()=>play(lastAnswer));
  $('#pause-answer').addEventListener('click',()=>{if(audio.src){if(audio.paused)audio.play().catch(()=>{});else audio.pause();}else if(speech){if(speech.paused)speech.resume();else speech.pause();}});
  $('#tutor-section').addEventListener('change',()=>{$('#return-paper').href=`/ipdf/${id}#${encodeURIComponent($('#tutor-section').value)}`;});
  const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Recognition){$('#dictate').disabled=true;$('#dictate').textContent='Speech input unavailable · type instead';}
  else $('#dictate').addEventListener('click',()=>{interrupt();if(recognition){recognition.stop();recognition=null;return;}recognition=new Recognition();recognition.lang='en-US';recognition.interimResults=false;recognition.onresult=event=>{$('#question').value=event.results[0][0].transcript;status('Question captured. Tap Ask the paper to send it.');};recognition.onerror=()=>status('Microphone unavailable. You can type your question.');recognition.onend=()=>{recognition=null;$('#dictate').textContent='🎙 Speak a question';};recognition.start();$('#dictate').textContent='Stop microphone';});
  $('#reset-memory').addEventListener('click',async()=>{interrupt();await api(`/api/tutor/${id}/reset`);await load();status('Tutor memory reset.');});
  window.addEventListener('pagehide',()=>{interrupt();recognition?.stop();});load().catch(e=>status(e.message));
})();
