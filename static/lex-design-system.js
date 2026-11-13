/* ════════════════════════════════════════════════════════════════════════
   LEX-INDIC — Design System runtime
   Loaded by every page after lex-design-system.css.  Self-initialising.
   ════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  if (window.__lexDesignSystem) return;   // _nav.html loads it on every page; some pages load it too
  window.__lexDesignSystem = true;

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
  const progressBar = document.getElementById('ds-progress') || document.createElement('div');
  progressBar.id = 'ds-progress';
  if (!progressBar.parentNode) document.body.appendChild(progressBar);
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
  const scrollBar = document.getElementById('ds-scroll-progress') || document.createElement('div');
  scrollBar.id = 'ds-scroll-progress';
  if (!scrollBar.parentNode) document.body.appendChild(scrollBar);
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

    if (e.defaultPrevented || a.dataset.noTransition !== undefined) return;
    const href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')
        || href.startsWith('javascript:')) return;

    // Same-origin pages only. A download (a file URL) never leaves the page,
    // so fading out for one would leave the page blank.
    let url;
    try {
      url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
    } catch { return; }
    if (/\.(docx?|pdf|csv|txt|xml|json|zip|xlsx?)$/i.test(url.pathname)
        || /\/(download|export)\b/i.test(url.pathname)) return;

    window.dsProgress.start();
    if (reduceMotion) return;  // honour reduced-motion: still progress bar, no fade

    e.preventDefault();
    document.body.classList.add('is-leaving');
    setTimeout(() => { window.location.href = url.href; }, 140);
    // If the browser stays here (the response was a download, or navigation
    // was cancelled), bring the page back.
    setTimeout(restorePage, 4000);
  });

  // Back/forward restores the page from the browser's cache exactly as it was
  // left — faded out — unless the leaving state is cleared here.
  function restorePage() {
    document.body.classList.remove('is-leaving');
    window.dsProgress.done();
  }
  window.addEventListener('pageshow', (e) => { if (e.persisted) restorePage(); });

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
     8) Entrance + hover motion for cards, tiles and panels on every page,
        including ones rendered later (results, tables). Styles live in
        lex-motion.css; nothing is hidden until this code has run.
     ────────────────────────────────────────────────────────────────────── */
  const CARD_SELECTOR = [
    '.card', '.ds-card', '.tile', '.tier-card', '.step', '.stat', '.stat-tile',
    '.sum-tile', '.totals-tile', '.meta-tile', '.what-card', '.why-card', '.problem-card',
    '.mock-card', '.panel', '.kpi', '.intake-card', '.flow-stage', '.case-card',
    '.lex-empty', '.empty-state', '.ruling', '.result-card', '.section-card',
    '#resultsAccordion > .accordion-item', '#loadStages > .load-stage',
  ].join(',');
  const NO_LIFT = '.accordion-item, .panel, .intake-card, .load-stage, .lex-empty, .empty-state, .flow-stage';
  // Elements that already animate themselves, or must never be hidden.
  const SKIP = '.reveal, .ds-reveal, .ds-reveal-stagger, .lex-topbar, .modal, .toast, ' +
               '.ds-toast-container, [data-no-motion], #chatPanel, .offcanvas, .dropdown-menu';

  if (!reduceMotion && 'IntersectionObserver' in window) {
    document.documentElement.classList.add('lx-motion');
    const pending = new Set();
    let batch = 0, batchTimer = null;
    const reveal = (el) => {
      if (!pending.delete(el)) return;
      // Stagger cards that arrive together (a grid scrolling into view).
      el.style.setProperty('--lx-delay', Math.min(batch, 6) * 70 + 'ms');
      batch++;
      el.classList.add('lx-in');
      io.unobserve(el);
      setTimeout(() => el.style.removeProperty('--lx-delay'), 1200);
      clearTimeout(batchTimer);
      batchTimer = setTimeout(() => { batch = 0; }, 120);
    };
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) if (entry.isIntersecting) reveal(entry.target);
    }, { threshold: 0 });   // any pixel: a card taller than the screen must still appear

    // Backstop: some browsers pause observers and animation frames (occluded
    // or embedded windows) while timers keep running. Layout still works, so
    // anything on screen is revealed from here — content can never stay hidden.
    setInterval(() => {
      if (!pending.size) return;
      const h = window.innerHeight;
      for (const el of [...pending]) {
        if (!el.isConnected) { pending.delete(el); continue; }
        const r = el.getBoundingClientRect();
        if ((r.width || r.height) && r.bottom > 0 && r.top < h) reveal(el);
      }
    }, 1000);

    const prepare = (root) => {
      const found = root.matches && root.matches(CARD_SELECTOR) ? [root] : [];
      if (root.querySelectorAll) found.push(...root.querySelectorAll(CARD_SELECTOR));
      for (const el of found) {
        if (el.dataset.lxSeen || el.closest(SKIP)) continue;
        el.dataset.lxSeen = '1';
        el.classList.add('lx-reveal');
        pending.add(el);
        io.observe(el);
        // Lift on hover: small, self-contained cards only (not big forms).
        if (!el.matches(NO_LIFT) && !el.querySelector('input, textarea, select')
            && el.offsetHeight > 0 && el.offsetHeight < 420) {
          el.classList.add('lx-lift');
        }
      }
    };
    prepare(document.body);
    window.lxReveal = prepare;

    // Cards added later (analysis results, fetched tables) animate in too.
    new MutationObserver((records) => {
      for (const r of records) for (const n of r.addedNodes) if (n.nodeType === 1) prepare(n);
    }).observe(document.body, { childList: true, subtree: true });
  }

  // Gold call-to-action buttons get a sheen on hover.
  document.querySelectorAll('.ds-btn-primary, .btn-gold, .btn-primary, .tier-btn.btn-gold, .lex-signin')
    .forEach((b) => b.classList.add('lx-sheen'));

  // "Loading…" placeholders shimmer until their content arrives.
  document.querySelectorAll('.empty, .loading, [data-loading]').forEach((el) => {
    if (/^\s*Loading…?\s*$/.test(el.textContent)) {
      el.classList.add('lx-skeleton');
      new MutationObserver((_, obs) => { el.classList.remove('lx-skeleton'); obs.disconnect(); })
        .observe(el, { childList: true, characterData: true, subtree: true });
    }
  });

  /* ──────────────────────────────────────────────────────────────────────
     9) Mark the active nav link automatically based on URL.
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
