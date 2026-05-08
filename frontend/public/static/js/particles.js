/**
 * AUREM — Gold Particles Background (hero canvas)
 *
 * Usage: drop <canvas id="aurem-particles"></canvas> as the first child
 * of any position:relative parent and add
 *   <script src="/static/js/particles.js" defer></script>
 * before </body>. The canvas sizes to its parent.
 */
(function () {
  const canvas = document.getElementById("aurem-particles");
  if (!canvas) return;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const ctx = canvas.getContext("2d");
  let W, H, particles = [], animId;

  const CFG = {
    count: 90,
    colors: [
      "rgba(212,175,55,",
      "rgba(255,215,0,",
      "rgba(180,140,30,",
      "rgba(255,245,180,",
    ],
    minR: 1,
    maxR: 3,
    speed: 0.3,
    connectionDist: 130,
    connectionOpacity: 0.07,
  };

  function resize() {
    const parent = canvas.parentElement;
    if (!parent) return;
    W = canvas.width = parent.offsetWidth;
    H = canvas.height = parent.offsetHeight;
    canvas.style.cssText =
      "position:absolute;inset:0;width:100%;height:100%;" +
      "pointer-events:none;z-index:1;";
  }

  function mkP() {
    const c = CFG.colors[Math.floor(Math.random() * CFG.colors.length)];
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      r: CFG.minR + Math.random() * (CFG.maxR - CFG.minR),
      vx: (Math.random() - 0.5) * CFG.speed,
      vy: (Math.random() - 0.5) * CFG.speed,
      color: c,
      alpha: 0.3 + Math.random() * 0.6,
      pulse: Math.random() * Math.PI * 2,
      ps: 0.008 + Math.random() * 0.018,
    };
  }

  function init() {
    particles = Array.from({ length: CFG.count }, mkP);
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < CFG.connectionDist) {
          const op = (1 - d / CFG.connectionDist) * CFG.connectionOpacity;
          ctx.beginPath();
          ctx.strokeStyle = "rgba(212,175,55," + op + ")";
          ctx.lineWidth = 0.4;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }

    particles.forEach(function (p) {
      p.pulse += p.ps;
      const g = Math.sin(p.pulse) * 0.25;
      const a = Math.min(1, p.alpha + g);

      const gr = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 5);
      gr.addColorStop(0, p.color + (0.12 + g * 0.08) + ")");
      gr.addColorStop(1, p.color + "0)");
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r * 5, 0, Math.PI * 2);
      ctx.fillStyle = gr;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color + a + ")";
      ctx.fill();

      p.x += p.vx;
      p.y += p.vy;
      if (p.x < -10) p.x = W + 10;
      if (p.x > W + 10) p.x = -10;
      if (p.y < -10) p.y = H + 10;
      if (p.y > H + 10) p.y = -10;
    });

    animId = requestAnimationFrame(draw);
  }

  function boot() {
    resize();
    init();
    draw();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.addEventListener("resize", function () {
    cancelAnimationFrame(animId);
    resize();
    draw();
  });
})();
