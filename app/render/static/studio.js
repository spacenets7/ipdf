(() => {
  'use strict';
  const form = document.querySelector('#create-form');
  const sourceInputs = form.querySelectorAll('[name=source]');
  sourceInputs.forEach(input => input.addEventListener('change', () => {
    document.querySelector('#arxiv-field').hidden = input.value !== 'arxiv';
    document.querySelector('#upload-field').hidden = input.value !== 'upload';
  }));
  document.querySelector('#sample-paper').addEventListener('click', () => { document.querySelector('#arxiv-id').value='1706.03762'; });
  document.querySelector('#pdf-file').addEventListener('change', event => { document.querySelector('#file-name').textContent = event.target.files[0]?.name || 'PDF · up to 25 MB'; });
  const button = document.querySelector('#create-button');
  const error = document.querySelector('#create-error');
  async function poll(job) {
    try {
      const response = await fetch(`/ipdf/status/${encodeURIComponent(job)}`);
      if (!response.ok) throw new Error('The job status is unavailable. Please try again.');
      const data = await response.json();
      document.querySelector('#job-message').textContent = data.message;
      document.querySelector('#job-percent').textContent = `${data.progress}%`;
      document.querySelector('#job-bar').style.width = `${data.progress}%`;
      if (data.state === 'ready') { sessionStorage.removeItem('ipdf-active-job'); location.assign(`/ipdf/${data.result_id}`); return; }
      if (data.state === 'error') { sessionStorage.removeItem('ipdf-active-job'); throw new Error(data.error || 'Could not open this paper.'); }
      setTimeout(() => poll(job), 1800);
    } catch (failure) {
      error.textContent = failure.message; error.hidden = false; button.disabled = false;
    }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault(); error.hidden = true;
    const selected = form.querySelector('[name=source]:checked').value;
    const file = document.querySelector('#pdf-file').files[0];
    if (selected === 'upload' && (!file || file.size > 25_000_000)) { error.textContent = 'Choose a PDF under 25 MB.'; error.hidden = false; return; }
    if (selected === 'arxiv' && !document.querySelector('#arxiv-id').value.trim()) { error.textContent = 'Enter an arXiv ID or choose a PDF to upload.'; error.hidden = false; return; }
    const body = new FormData();
    body.append('level', form.querySelector('[name=level]:checked').value);
    if (selected === 'upload') body.append('pdf', file); else body.append('arxiv_id', document.querySelector('#arxiv-id').value);
    button.disabled = true;
    try {
      const response = await fetch('/ipdf/create', {method:'POST',body});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your paper and try again.');
      document.querySelector('#job-progress').hidden = false;
      sessionStorage.setItem('ipdf-active-job', data.job_id);
      poll(data.job_id);
    } catch (failure) { error.textContent=failure.message; error.hidden=false; button.disabled=false; }
  });
  const active = sessionStorage.getItem('ipdf-active-job');
  if (active) { button.disabled=true; document.querySelector('#job-progress').hidden=false; poll(active); }
})();
