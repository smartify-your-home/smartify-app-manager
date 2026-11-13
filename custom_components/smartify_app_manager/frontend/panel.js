/** Smartify App Manager v0.1.0 – standalone, theme-aware Home Assistant panel. */
class SmartifyAppManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: 'open'});
    this._busy = false;
    this._apps = [];
    this._pinConfigured = false;
    this._loaded = false;
    this._error = '';
    this._success = '';
  }
  set hass(value) {
    this._hass = value;
    if (!this._loaded && !this._busy) this.refresh();
  }
  async refresh() {
    if (!this._hass || this._busy) return;
    this._busy = true;
    try {
      const data = await this._hass.callWS({type: 'smartify_app_manager/catalog'});
      this._apps = data.apps;
      this._pinConfigured = data.pin_configured;
      this._loaded = true;
      this._error = '';
    } catch (err) { this._error = String(err.message || err); }
    finally { this._busy = false; this.render(); }
  }
  render() {
    const escape = v => String(v ?? '').replace(/[&<>"']/g, ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
        .wrap{max-width:1100px;margin:auto;padding:24px 18px 48px}.head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
        h1{font-size:27px;letter-spacing:-.5px;margin:0}h2{font-size:17px;margin:0 0 12px}p{color:var(--secondary-text-color);margin:6px 0 0}.count{font-weight:700}
        .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:22px}.panel{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,14px);padding:18px;margin-top:16px;box-shadow:var(--ha-card-box-shadow,none)}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:13px;margin-top:14px}.app{border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,12px);padding:16px;display:flex;flex-direction:column;gap:14px;min-width:0}
        .apphead{display:flex;align-items:center;gap:12px}.logo{border-radius:12px;background:var(--secondary-background-color);padding:10px;font-size:22px}.name{font-weight:650}.meta{font-size:12px;color:var(--secondary-text-color);margin-top:4px}.buttons{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
        button,a.button{font:inherit;font-size:13px;border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,8px);padding:9px 12px;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer;text-decoration:none}
        button.primary{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
        input{background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);padding:10px;border-radius:8px;max-width:230px}.tag{font-size:11px;border:1px solid var(--divider-color);border-radius:20px;padding:3px 8px;display:inline-block}.warn{color:var(--error-color)}.ok{color:var(--success-color,var(--primary-color))}.notice{font-size:13px;line-height:1.5}.pinrow{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:12px}
      </style>
      <main class="wrap">
        <div class="head"><div><h1>Smartify App Manager</h1><p>Zentrale Übersicht deiner Smartify-Erweiterungen</p></div><span class="tag">v0.1.0 · ohne Testzeitraum</span></div>
        <div class="controls"><span class="count">${this._apps.length} Module im Katalog</span><button id="refresh">Aktualisieren</button></div>
        ${this._error?`<p class="warn" role="alert">${escape(this._error)}</p>`:''}${this._success?`<p class="ok" role="status">${escape(this._success)}</p>`:''}
        <section class="panel"><h2>Smartify Apps</h2><div class="notice">Installation und Updates erfolgen über Home Assistant / HACS. Hier kannst du das jeweilige Repository öffnen. „Sperren“ ist derzeit nur ein Verwaltungskennzeichen und <strong>deaktiviert keine laufende Integration</strong>.</div>
          <div class="grid">${this._apps.map(app=>`<article class="app"><div class="apphead"><span class="logo">${({'energy-pro':'⚡','flow-card':'🔀','weather-card':'☁️','person-detection':'📷','floorplan3d':'🏠','sip-manager':'☎️','themes':'🎨','heating':'🌡️','raffstore':'🪟','tailnet-viewer':'🌐','tabbar':'📑','row-card':'▤'})[app.id]||'◼'}</span><div><div class="name">${escape(app.name)}</div><div class="meta">${escape(app.category)} · ${app.locked?'🔒 Gesperrt (Kennzeichen)':'Verfügbar'}</div></div></div><div class="buttons"><a class="button" href="${escape(app.url)}" target="_blank" rel="noopener noreferrer">Repository / Installation ↗</a><button data-id="${escape(app.id)}" data-locked="${app.locked?'false':'true'}">${app.locked?'Entsperren':'Sperren'}</button></div></article>`).join('')}</div>
        </section>
        <section class="panel"><h2>Administrator-PIN</h2><p class="notice">Mindestens 6 Zeichen. PIN schützt die Änderung der Modul-Kennzeichen. Die Anmeldung als HA-Administrator ist zusätzlich erforderlich.</p><div class="pinrow">${this._pinConfigured?'<input type="password" id="old" placeholder="Bisherige PIN" autocomplete="off">':''}<input type="password" id="new" placeholder="Neue PIN (mind. 6)" autocomplete="new-password"><button id="setpin">${this._pinConfigured?'PIN ändern':'PIN einrichten'}</button></div></section>
      </main>`;
    this.shadowRoot.querySelector('#refresh').onclick=()=>this.refresh();
    this.shadowRoot.querySelector('#setpin').onclick=()=>this.setPin();
    this.shadowRoot.querySelectorAll('button[data-id]').forEach(button=>button.onclick=()=>this.setLock(button.dataset.id,button.dataset.locked==='true'));
  }
  async setPin(){
    const new_pin=this.shadowRoot.querySelector('#new').value;
    const old_pin=this.shadowRoot.querySelector('#old')?.value||'';
    if(new_pin.length<6){this._error='PIN muss mindestens 6 Zeichen enthalten.';this.render();return;}
    try {await this._hass.callWS({type:'smartify_app_manager/set_pin',new_pin,old_pin});this._success='PIN gespeichert.';await this.refresh();}
    catch(err){this._error=String(err.message||err);this.render();}
  }
  async setLock(app_id,locked){
    if(!this._pinConfigured){this._error='Bitte zuerst Administrator-PIN einrichten.';this.render();return;}
    const pin=window.prompt('Smartify Administrator-PIN:');
    if(pin===null)return;
    try {await this._hass.callWS({type:'smartify_app_manager/set_lock',app_id,locked,pin});this._success=locked?'Modul als gesperrt markiert.':'Modulkennzeichen entsperrt.';await this.refresh();}
    catch(err){this._error=String(err.message||err);this.render();}
  }
}
customElements.define('smartify-app-manager-panel',SmartifyAppManagerPanel);
