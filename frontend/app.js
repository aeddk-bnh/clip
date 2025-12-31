document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('processForm');
  const result = document.getElementById('result');
  const preview = document.getElementById('preview');
  const clipsEl = document.getElementById('clips');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    result.textContent = 'Queuing...';
    const url = document.getElementById('videoUrl').value;
    const platform = document.getElementById('platform').value;

    try {
      const resp = await fetch('/process-by-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_url: url, platform }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        result.textContent = 'Error: ' + (data.detail || JSON.stringify(data));
        return;
      }
      result.innerHTML = `Queued job: <strong>${data.video_id}</strong> — status: ${data.status}`;

      // start polling status
      const jobId = data.video_id;
      clipsEl.innerHTML = '';
      preview.style.backgroundImage = '';

      const poll = setInterval(async () => {
        try {
          const s = await fetch(`/status/${jobId}`);
          if (!s.ok) return;
          const st = await s.json();
          result.textContent = `Job ${jobId} — ${st.status}`;
          if (st.thumbnail) {
            preview.style.backgroundImage = `url(${st.thumbnail})`;
            preview.classList.add('has-thumb');
          }
          if (st.status === 'finished' || st.status === 'error') {
            clearInterval(poll);
            if (st.status === 'finished') {
              result.textContent = `Job ${jobId} — finished (${st.clips_count || 0} clips)`;
              // fetch clips list
              const c = await fetch(`/clips/${jobId}`);
              if (c.ok) {
                const cj = await c.json();
                if (cj.clips && cj.clips.length) {
                  clipsEl.innerHTML = '';
                  cj.clips.forEach(cl => {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'clip';
                    const vid = document.createElement('video');
                    vid.controls = true;
                    vid.src = cl.url;
                    vid.width = 320;
                    wrapper.appendChild(vid);
                    const meta = document.createElement('div');
                    meta.className = 'clip-meta';
                    meta.textContent = cl.meta && cl.meta.start ? `start: ${cl.meta.start}s` : '';
                    wrapper.appendChild(meta);
                    clipsEl.appendChild(wrapper);
                  });
                } else {
                  clipsEl.textContent = 'No clips produced.';
                }
              }
            } else {
              result.textContent = `Job ${jobId} — error`; 
            }
          }
        } catch (err) {
          console.error(err);
        }
      }, 2000);
    } catch (err) {
      result.textContent = 'Request failed: ' + err.message;
    }
  });
});