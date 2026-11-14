import { api } from './api.js';
const msg = document.getElementById('msg');
document.getElementById('go').addEventListener('click', async () => {
  try {
    const { request_id } = await api('/api/pair/request', { method: 'POST', body: { code: document.getElementById('code').value.trim(), name: document.getElementById('name').value.trim() } });
    msg.textContent = 'Waiting for approval on the computer…';
    const timer = setInterval(async () => {
      try {
        const s = await api('/api/pair/status?id=' + encodeURIComponent(request_id));
        if (s.status === 'approved') { clearInterval(timer); localStorage.setItem('crysta_token', s.token); msg.textContent = 'Paired! Opening Crysta…'; setTimeout(() => (location.href = '/'), 800); }
        else if (s.status === 'denied' || s.status === 'unknown') { clearInterval(timer); msg.textContent = 'The computer declined the request.'; }
      } catch (e) { clearInterval(timer); msg.textContent = e.message; }
    }, 1500);
  } catch (e) { msg.textContent = e.message; }
});
