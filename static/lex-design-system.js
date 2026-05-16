/* ════════════════════════════════════════════════════════════════════════
   LEX-INDIC — Design System runtime
   Loaded by every page after lex-design-system.css.  Self-initialising.
   ════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── Honour reduced-motion preference once at load ──────────────────── */
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ──────────────────────────────────────────────────────────────────────
     1) Scroll-reveal — uses IntersectionObserver, no scroll listeners.
        Marks any element with .ds-reveal or .ds-reveal-stagger as
        .is-visible once it enters the viewport.
     ────────────────────────────────────────────────────────────────────── */
  const revealEls = document.querySelectorAll('.ds-reveal, .ds-reveal-stagger');
  if (revealEls.length && 'IntersectionObserver' in window && !reduceMotion) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add('is-visible'));
  }

  /* ──────────────────────────────────────────────────────────────────────
     2) Top progress bar — gold shimmer slides across during navigation
        and any time JS calls window.dsProgress.start() / .done().
     ────────────────────────────────────────────────────────────────────── */
  const progressBar = document.createElement('div');
  progressBar.id = 'ds-progress';
  document.body.appendChild(progressBar);
  let progressTimer = null;
  window.dsProgress = {
    start() {
      progressBar.classList.add('active');
      progressBar.style.width = '25%';
      clearTimeout(progressTimer);
      progressTimer = setTimeout(() => { progressBar.style.width = '70%'; }, 350);
    },
    done() {
      progressBar.style.width = '100%';
      setTimeout(() => {
        progressBar.classList.remove('active');
        progressBar.style.width = '0%';
      }, 240);
    },
  };

  /* ──────────────────────────────────────────────────────────────────────
     3) Scroll-progress bar — thin gradient ticks along as the user scrolls.
        Throttled via rAF so it doesn't fire on every scroll event.
     ────────────────────────────────────────────────────────────────────── */
  const scrollBar = document.createElement('div');
  scrollBar.id = 'ds-scroll-progress';
  document.body.appendChild(scrollBar);
  let scrollRaf = null;
  window.addEventListener('scroll', () => {
    if (scrollRaf) return;
    scrollRaf = requestAnimationFrame(() => {
      const docH = document.documentElement.scrollHeight - window.innerHeight;
      const pct = docH > 0 ? (window.scrollY / docH) * 100 : 0;
      scrollBar.style.width = pct.toFixed(2) + '%';
      scrollRaf = null;
    });
  }, { passive: true });

  /* ──────────────────────────────────────────────────────────────────────
     4) Smooth page transitions — when a same-origin link is clicked,
        fade the body out, navigate, fade back in.  Also kicks off the
        top progress bar so the user gets an immediate visual ack.
     ────────────────────────────────────────────────────────────────────── */
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    if (a.target === '_blank' || a.hasAttribute('download')) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    const href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

    // Same-origin only
    try {
      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
    } catch { return; }

    window.dsProgress.start();
    if (reduceMotion) return;  // honour reduced-motion: still progress bar, no fade

    e.preventDefault();
    document.body.classList.add('is-leaving');
    setTimeout(() => { window.location.href = href; }, 140);
  });

  /* ──────────────────────────────────────────────────────────────────────
     5) Toast helper — window.dsToast(message, kind)
        kind: 'ok' | 'err' | 'warn' (default neutral)
     ────────────────────────────────────────────────────────────────────── */
  let toastContainer = null;
  function ensureToastContainer() {
    if (toastContainer) return toastContainer;
    toastContainer = document.createElement('div');
    toastContainer.className = 'ds-toast-container';
    toastContainer.setAttribute('role', 'status');
    toastContainer.setAttribute('aria-live', 'polite');
    document.body.appendChild(toastContainer);
    return toastContainer;
  }

  window.dsToast = function dsToast(message, kind, durationMs) {
    const c = ensureToastContainer();
    const t = document.createElement('div');
    t.className = 'ds-toast' + (kind ? ' ' + kind : '');
    t.textContent = message;
    c.appendChild(t);

    const ms = durationMs || 4200;
    setTimeout(() => {
      t.classList.add('fade-out');
      setTimeout(() => t.remove(), 250);
    }, ms);
  };

  /* ──────────────────────────────────────────────────────────────────────
     6) Auto-focus rings on keyboard, not mouse.
        Body gets .ds-keyboard while the user is tabbing; CSS hooks can
        use it to draw stronger focus rings without affecting click users.
     ────────────────────────────────────────────────────────────────────── */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') document.body.classList.add('ds-keyboard');
  });
  document.addEventListener('mousedown', () => {
    document.body.classList.remove('ds-keyboard');
  });

  /* ──────────────────────────────────────────────────────────────────────
     7) Tiny utility: convert a plain promise into a button "loading" state
        Usage:   dsWithLoading(btnEl, () => fetch(...))
     ────────────────────────────────────────────────────────────────────── */
  window.dsWithLoading = async function dsWithLoading(btnEl, work) {
    if (!btnEl) return work();
    const original = btnEl.innerHTML;
    btnEl.disabled = true;
    btnEl.innerHTML = '<span class="ds-spinner"></span><span>Loading…</span>';
    try { return await work(); }
    finally { btnEl.disabled = false; btnEl.innerHTML = original; }
  };

  /* ──────────────────────────────────────────────────────────────────────
     8) Mark the active nav link automatically based on URL.
     ────────────────────────────────────────────────────────────────────── */
  const path = window.location.pathname;
  document.querySelectorAll('.ds-nav-link').forEach((a) => {
    try {
      const u = new URL(a.href, window.location.href);
      if (u.pathname === path || (u.pathname !== '/' && path.startsWith(u.pathname))) {
        a.classList.add('active');
      }
    } catch { /* ignore */ }
  });

})();
