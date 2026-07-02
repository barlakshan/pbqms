/* =====================================================
   People's Bank QEMS — Display Screen JS
   Real-time TV/kiosk board with WebSocket
   ===================================================== */

const QueueDisplay = (() => {
  let socket = null;
  let branchCode = null;
  let voiceEnabled = false;

  function init(code, enableVoice = false) {
    branchCode  = code;
    voiceEnabled = enableVoice;
    connectSocket();
    startClock();
    poll();
  }

  function connectSocket() {
    socket = io({ transports: ['websocket', 'polling'] });
    socket.on('connect', () => socket.emit('join_branch_display', { branch_code: branchCode }));
    socket.on('queue_update', handleUpdate);
    socket.on('disconnect', () => setTimeout(connectSocket, 3000));
  }

  function handleUpdate(data) {
    if (!data.serving || !data.serving.length) return;

    const primary = data.serving[0];
    animateToken(primary.token);

    document.getElementById('d-token').textContent   = primary.token;
    document.getElementById('d-name').textContent    = primary.customer_name;
    document.getElementById('d-counter').textContent = primary.counter;

    const priBadge = document.getElementById('d-priority');
    if (priBadge) {
      priBadge.style.display = primary.is_priority ? 'inline-block' : 'none';
      priBadge.textContent = `★ Priority — ${primary.priority_reason}`;
    }

    updateNextList(data.serving.slice(1));
    if (voiceEnabled) announce(primary);

    document.getElementById('d-waiting-count').textContent = data.waiting_count;
  }

  function poll() {
    fetch(`/api/queue/display/${branchCode}`)
    .then(r => r.json())
    .then(data => {
      if (data.serving && data.serving.length) handleUpdate(data);
    })
    .catch(() => {})
    .finally(() => setTimeout(poll, 20000));
  }

  function updateNextList(serving) {
    const el = document.getElementById('d-next-list');
    if (!el) return;
    el.innerHTML = serving.slice(0, 4).map(t => `
      <div style="display:flex;align-items:center;justify-content:space-between;
                  padding:6px 0;border-bottom:0.5px solid rgba(255,255,255,.06);">
        <span style="font-size:14px;font-weight:600;color:rgba(255,255,255,.8);">${t.token}</span>
        <span style="font-size:10px;color:rgba(255,255,255,.4);">${t.customer_name}</span>
        <span style="font-size:10px;color:rgba(255,255,255,.35);">${t.counter}</span>
      </div>
    `).join('');
  }

  function animateToken(token) {
    const el = document.getElementById('d-token');
    if (!el) return;
    el.style.opacity = '0';
    el.style.transform = 'scale(.85)';
    setTimeout(() => {
      el.textContent = token;
      el.style.transition = 'opacity .35s, transform .35s';
      el.style.opacity = '1';
      el.style.transform = 'scale(1)';
    }, 200);
  }

  function announce(data) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const text = data.is_priority
      ? `Priority customer. Token ${data.token.split('').join(' ')}. ${data.customer_name}. Please proceed to ${data.counter}. Priority customer — please assist immediately.`
      : `Token ${data.token.split('').join(' ')}. ${data.customer_name}. Please proceed to ${data.counter}.`;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = 'en-US';
    utter.rate = 0.88;
    window.speechSynthesis.speak(utter);
  }

  function startClock() {
    const update = () => {
      const el = document.getElementById('d-clock');
      if (el) {
        const now = new Date();
        el.textContent = now.toLocaleTimeString('en-LK', { hour: '2-digit', minute: '2-digit' });
      }
    };
    update();
    setInterval(update, 1000);
  }

  return { init };
})();
