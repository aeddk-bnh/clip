document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('processForm');
  const result = document.getElementById('result');
  const preview = document.getElementById('preview');
  const clipsEl = document.getElementById('clips');
  let _currentThumbRatio = null;
  let _resizeHandler = null;

  async function fitPreviewToImageUrl(url) {
    if (!url) {
      preview.style.backgroundImage = '';
      preview.style.height = '';
      _currentThumbRatio = null;
      if (_resizeHandler) { window.removeEventListener('resize', _resizeHandler); _resizeHandler = null; }
      return;
    }

    // Helper to set background and height
    const applyImageUrl = (imgUrl, naturalW, naturalH) => {
      _currentThumbRatio = (naturalW && naturalH) ? (naturalW / naturalH) : null;
      preview.style.backgroundImage = `url(${imgUrl})`;
      const setHeight = () => {
        const rect = preview.getBoundingClientRect();
        const width = rect.width || preview.offsetWidth || preview.clientWidth;
        if (width && _currentThumbRatio) {
          preview.style.height = (width / _currentThumbRatio) + 'px';
        }
      };
      setHeight();
      if (_resizeHandler) window.removeEventListener('resize', _resizeHandler);
      _resizeHandler = () => setHeight();
      window.addEventListener('resize', _resizeHandler);
    };

    try {
      // fetch via backend proxy to avoid CORS and allow canvas processing
      const proxyUrl = url.startsWith('/') ? url : `/proxy-thumbnail?url=${encodeURIComponent(url)}`;
      const resp = await fetch(proxyUrl);
      if (!resp.ok) {
        applyImageUrl(url);
        return;
      }
      const blob = await resp.blob();
      const objectUrl = URL.createObjectURL(blob);

      // load image from blob
      const img = new Image();
      img.src = objectUrl;
      await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });
      const w = img.naturalWidth || img.width;
      const h = img.naturalHeight || img.height;
      if (!w || !h) {
        URL.revokeObjectURL(objectUrl);
        applyImageUrl(objectUrl);
        return;
      }

      // draw to canvas and detect black/near-black bars at top/bottom
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0);
      try {
        const imgd = ctx.getImageData(0, 0, w, h);
        const data = imgd.data;
        const sampleStep = Math.max(1, Math.floor(w / 50));
        const rowThreshold = 10; // minimal mean brightness to consider non-black

        const rowMean = (row) => {
          let sum = 0;
          let count = 0;
          for (let x = 0; x < w; x += sampleStep) {
            const idx = (row * w + x) * 4;
            const r = data[idx], g = data[idx+1], b = data[idx+2];
            // perceived luminance
            const lum = 0.2126*r + 0.7152*g + 0.0722*b;
            sum += lum; count++;
          }
          return sum / Math.max(1, count);
        };

        let top = 0, bottom = h - 1;
        // scan from top
        for (let y = 0; y < h; y++) {
          if (rowMean(y) > rowThreshold) { top = y; break; }
        }
        // scan from bottom
        for (let y = h - 1; y >= 0; y--) {
          if (rowMean(y) > rowThreshold) { bottom = y; break; }
        }

        // if there are significant black bars, crop them
        const minVisibleHeight = 10; // avoid degenerate crop
        if (bottom - top + 1 >= minVisibleHeight && (top > 0 || bottom < h - 1)) {
          const cropH = (bottom - top + 1);
          const out = document.createElement('canvas');
          out.width = w; out.height = cropH;
          const octx = out.getContext('2d');
          octx.drawImage(c, 0, top, w, cropH, 0, 0, w, cropH);
          // convert to blob and use as background
          const croppedUrl = URL.createObjectURL(await new Promise(res => out.toBlob(res, 'image/jpeg', 0.9)));
          URL.revokeObjectURL(objectUrl);
          applyImageUrl(croppedUrl, w, cropH);
          return;
        }
      } catch (e) {
        // reading image data can fail if not allowed; fallback to using proxied image directly
        console.warn('canvas imageData failed', e);
      }

      // no cropping needed
      applyImageUrl(objectUrl, w, h);
    } catch (err) {
      console.error('preview load failed', err);
      // fallback: use original url
      applyImageUrl(url);
    }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    result.textContent = 'Queuing...';
    const url = document.getElementById('videoUrl').value;
    const platform = document.getElementById('platform').value;
    // show provider preview immediately (YouTube fallback) to avoid black background
    const providerPreview = getProviderThumbnail(url);
    if (providerPreview) {
      fitPreviewToImageUrl(providerPreview);
      preview.classList.add('has-thumb');
    }

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
      // If we couldn't determine a provider thumbnail for this new URL,
      // clear any previous preview so it doesn't show the old video's image.
      if (!providerPreview) {
        preview.style.backgroundImage = '';
        preview.classList.remove('has-thumb');
      }

      const poll = setInterval(async () => {
        try {
          const s = await fetch(`/status/${jobId}`);
          if (!s.ok) return;
          const st = await s.json();
          result.textContent = `Job ${jobId} — ${st.status}`;
          if (st.thumbnail) {
            preview.classList.add('has-thumb');
            // Fit preview to actual thumbnail dimensions by loading it in-browser
            fitPreviewToImageUrl(st.thumbnail);
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
  
  function getProviderThumbnail(url) {
    try {
      // YouTube id
      const yt = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/))([A-Za-z0-9_-]{11})/);
      if (yt && yt[1]) return `https://img.youtube.com/vi/${yt[1]}/hqdefault.jpg`;
    } catch (e) {}
    return null;
  }
});