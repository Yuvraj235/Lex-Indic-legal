// Admin token handling for the operator pages (/dashboard, /admin/soc2).
// The token lives in this tab's sessionStorage and leaves the browser only as
// the X-Admin-Token header — never in a URL, where it would end up in server
// logs, proxies and browser history.
(function () {
  try { localStorage.removeItem('lexindic.admin_token'); } catch (e) {}  // pre-header versions kept it here

  const KEY = 'lexindic.admin_token';
  window.lexAdmin = {
    token() {
      try { return sessionStorage.getItem(KEY) || ''; } catch (e) { return ''; }
    },
    save(t) {
      try { sessionStorage.setItem(KEY, t); } catch (e) {}
    },
    fetch(url, opts = {}) {
      const headers = new Headers(opts.headers || {});
      const t = this.token();
      if (t) headers.set('X-Admin-Token', t);
      return fetch(url, Object.assign({}, opts, { headers }));
    },
    // Replace `el`'s content with a token prompt; `onSaved` runs after saving.
    prompt(el, onSaved) {
      el.innerHTML = `
        <div style="text-align:center;padding:40px">
          <h2 style="font-size:20px;margin-bottom:10px">Admin token required</h2>
          <p style="font-size:14px;margin:0 auto 14px;max-width:460px">
            Paste the ADMIN_TOKEN value from the server's environment.
            It is kept for this tab only.</p>
          <input type="password" id="lexAdminToken" autocomplete="off"
                 placeholder="ADMIN_TOKEN" style="width:260px;padding:8px 10px">
          <button type="button" id="lexAdminSave" style="margin-left:6px;padding:8px 16px">Unlock</button>
        </div>`;
      el.querySelector('#lexAdminSave').addEventListener('click', () => {
        const t = el.querySelector('#lexAdminToken').value.trim();
        if (t) { this.save(t); onSaved(); }
      });
    },
  };
})();
