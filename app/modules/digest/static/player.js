(() => {
  'use strict';
  const toast = document.querySelector('#toast');
  let toastTimer;
  function notify(message) {
    toast.textContent = message; toast.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.hidden = true; }, 6500);
  }
  async function request(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your preferences and try again.');
    return data;
  }
  document.querySelector('#preferences-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    if (!fields.getAll('topics').length && !String(fields.get('custom_topics')).trim()) {
      notify('Choose a topic or add one of your own.'); return;
    }
    const button = form.querySelector('button[type=submit]');
    button.disabled = true; document.querySelector('#form-status').hidden = false;
    try {
      // Save the profile without following the redirect into a potentially long build.
      const response = await fetch('/start', { method:'POST', body:fields });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the form.');
      }
      window.location.assign('/digest');
    } catch (error) {
      notify(error.message); button.disabled = false; document.querySelector('#form-status').hidden = true;
    }
  });
  document.querySelectorAll('.feedback').forEach(group => {
    group.querySelectorAll('button').forEach(button => button.addEventListener('click', async () => {
      const buttons = group.querySelectorAll('button');
      buttons.forEach(b => { b.disabled = true; });
      try {
        const data = await request('/feedback', { method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({item_id:Number(group.dataset.item),signal:button.dataset.signal}) });
        buttons.forEach(b => b.classList.toggle('selected', b === button));
        notify(data.duplicate ? 'Already noted. Thanks for helping us find your pace.' : `Noted. Future digests will adapt to you. Reading level: ${data.level}.`);
      } catch (error) { notify(error.message); }
      finally { buttons.forEach(b => { b.disabled = false; }); }
    }));
  });
  let audioBusy = false;
  const player = document.querySelector('#audio-player');
  const dock = document.querySelector('#audio-dock');
  document.querySelectorAll('.listen-button').forEach(button => button.addEventListener('click', async () => {
    if (audioBusy) { notify('An audio track is already being prepared.'); return; }
    audioBusy = true; const label = button.innerHTML;
    button.disabled = true; button.textContent = 'Preparing audio…';
    notify('Turning this read into a listen. Local narration can take a moment.');
    try {
      const data = await request(button.dataset.url, {method:'POST'});
      document.querySelector('#audio-title').textContent = button.dataset.title;
      document.querySelector('#audio-provider').textContent = `${data.provider} · ${data.cached ? 'saved audio' : 'freshly narrated'}`;
      player.src = data.url; dock.hidden = false;
      player.playbackRate = Number(document.querySelector('#audio-speed').value);
      try { await player.play(); } catch { notify('Audio is ready. Press play to listen.'); }
      if (data.message) notify(data.message);
    } catch (error) { notify(error.message); }
    finally { audioBusy = false; button.disabled = false; button.innerHTML = label; }
  }));
  document.querySelector('#audio-speed').addEventListener('change', event => { player.playbackRate = Number(event.target.value); });
  document.querySelector('#close-player').addEventListener('click', () => { player.pause(); dock.hidden = true; });
  player.addEventListener('error', () => notify('This audio file could not be played. Try preparing it again.'));
  document.querySelectorAll('.refresh-digest').forEach(button => button.addEventListener('click', async () => {
    button.disabled = true;
    try { await request('/digest/refresh', {method:'POST'}); window.location.reload(); }
    catch(error) { notify(error.message); button.disabled = false; }
  }));
  if (document.querySelector('[data-poll=true]')) {
    let failures = 0;
    const poll = async () => {
      try {
        const result = await request('/digest/status'); failures = 0;
        if (result.state === 'ready' || result.state === 'error') { window.location.reload(); return; }
      } catch { if (++failures === 3) notify('Connection paused. We will keep checking your digest.'); }
      setTimeout(poll, 2500);
    };
    setTimeout(poll, 2500);
  }
})();
