/* AUREM Trust Badge v1.0
 * Embed this script on your website to show a live "Monitored by AUREM" badge.
 * Usage: <script src="https://aurem.live/api/static/aurem-badge.js" data-bin="YOUR-BIN"></script>
 * The badge renders bottom-right, shows 30-day uptime %, and links to /monitor-free.
 */
(function () {
  var s = document.currentScript;
  if (!s) return;
  var bin = s.getAttribute('data-bin') || '';
  if (!bin) return;

  var API = (function () {
    try {
      var u = new URL(s.src);
      return u.origin;
    } catch (e) { return 'https://aurem.live'; }
  })();

  var css = '\
.aurem-badge{position:fixed;bottom:18px;right:18px;z-index:999999;\
display:inline-flex;align-items:center;gap:8px;padding:10px 16px;\
background:rgba(13,13,13,0.92);color:#E8E0D0;border:1px solid rgba(201,168,76,0.35);\
border-radius:999px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;\
font-size:12px;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);\
box-shadow:0 8px 24px rgba(0,0,0,0.25);text-decoration:none;cursor:pointer;\
transition:transform .18s ease,box-shadow .18s ease}\
.aurem-badge:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(201,168,76,0.3)}\
.aurem-badge-dot{width:8px;height:8px;border-radius:50%;background:#4ADE80;\
box-shadow:0 0 8px rgba(74,222,128,0.6);animation:aurem-pulse 2s ease-in-out infinite}\
.aurem-badge-dot.down{background:#EF4444;box-shadow:0 0 8px rgba(239,68,68,0.6)}\
.aurem-badge-brand{font-weight:700;color:#C9A84C;letter-spacing:0.04em}\
.aurem-badge-sub{color:#aaa;font-size:11px}\
@keyframes aurem-pulse{0%,100%{opacity:1}50%{opacity:0.5}}\
@media (max-width:640px){.aurem-badge{font-size:11px;padding:8px 12px;bottom:12px;right:12px}}';

  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // Render shell
  var a = document.createElement('a');
  a.className = 'aurem-badge';
  a.href = API + '/monitor-free?ref=badge&bin=' + encodeURIComponent(bin);
  a.target = '_blank';
  a.rel = 'noopener';
  a.setAttribute('data-aurem-badge', '1');
  a.innerHTML = '<span class="aurem-badge-dot"></span>' +
    '<span class="aurem-badge-brand">AUREM</span>' +
    '<span class="aurem-badge-sub">uptime --%</span>';
  document.body.appendChild(a);

  // Fetch live uptime
  function update() {
    fetch(API + '/api/public/site-monitor/badge-data/' + encodeURIComponent(bin))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;
        var sub = a.querySelector('.aurem-badge-sub');
        var dot = a.querySelector('.aurem-badge-dot');
        if (sub) sub.textContent = (d.uptime_pct != null ? d.uptime_pct + '% uptime' : 'monitored');
        if (dot) dot.className = 'aurem-badge-dot' + (d.status === 'down' ? ' down' : '');
      })
      .catch(function () {});
  }
  update();
  setInterval(update, 5 * 60 * 1000); // every 5 min
})();
