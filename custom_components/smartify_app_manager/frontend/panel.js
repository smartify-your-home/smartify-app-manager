/** Authentic Smartify icons as published by their original repositories. */
const SMARTIFY_ORIGINAL_ICONS = Object.freeze({
  'energy-pro': 'smartify-energy-pro/main/custom_components/smartify_energy/brand/icon.png',
  'flow-card': 'smartify-flow-card/main/custom_components/smartify_flow_card/brand/icon.png',
  'weather-card': 'smartify-weather-card/main/images/icon.png',
  'person-detection': 'smartify-person-detection/main/images/icon.png',
  'sip-manager': 'smartify-sip-manager/main/images/icon.png',
  'heating': 'smartify-heating/main/custom_components/smartify_heating/brand/icon.png',
  'raffstore': 'smartify-raffstore/main/images/icon.png',
  'tailnet-viewer': 'smartify-tailnet-viewer/main/images/icon.png',
  'tabbar': 'smartify-tabbar/main/images/icon.png',
});
const SMARTIFY_FALLBACK_ICONS = Object.freeze({
  'energy-pro':'mdi:solar-power', 'flow-card':'mdi:transit-connection-variant',
  'weather-card':'mdi:weather-partly-cloudy',
  'person-detection':'mdi:account-eye', 'floorplan3d':'mdi:floor-plan',
  'sip-manager':'mdi:phone', 'themes':'mdi:palette',
  'heating':'mdi:radiator', 'raffstore':'mdi:blinds',
  'tailnet-viewer':'mdi:lan', 'tabbar':'mdi:tab',
  'row-card':'mdi:table-row',
});
/** Smartify App Manager v0.3.0 – standalone, theme-aware Home Assistant panel. */
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
    this._lastSynced = null;
    this._syncError = null;
    this._kubi = {configured:false,connected:false,url:''};
    this._downloadInfo = null;
    this._pollTimer = null;
  }
  connectedCallback() {
    if (this._pollTimer !== null) return;
    this._pollTimer = setInterval(() => {
      // Refresh the visible panel; backend update entity also polls on its own.
      if (this._loaded && !this._busy
          && this.shadowRoot.activeElement?.id !== 'kubi-url') {
        this.checkKubi();
      }
    }, 120000);
  }
  disconnectedCallback() {
    if (this._pollTimer !== null) clearInterval(this._pollTimer);
    this._pollTimer = null;
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
      this._lastSynced = data.last_synced;
      this._syncError = data.sync_error;
      this._loaded = true;
      this._error = '';
    } catch (err) { this._error = String(err.message || err); }
    finally { this._busy = false; this.render(); }
    if (this._loaded) await this.checkKubi();
  }
  async checkKubi() {
    if (!this._hass) return;
    try {
      this._kubi = await this._hass.callWS({type:'smartify_app_manager/kubi_status'});
    } catch (err) {
      this._kubi = {configured:true,connected:false,url:this._kubi.url || '',error:String(err.message||err)};
    }
    this.render();
  }
  kubiPanel(escape) {
    const k=this._kubi;
    const status = k.connected
      ? '<span class="ok">● Verbunden</span> · Cubi SEP <strong>'+escape(k.version)+'</strong>'
        + (k.installed_version?' · Installiert: <strong>'+escape(k.installed_version)+'</strong>':' · SEP nicht installiert')
        + ' · SHA-256 '+escape((k.sha256||'').slice(0,12))+'…'
      : k.configured
        ? '<span class="warn">● Nicht erreichbar</span> · '+escape(k.error||'Bitte Verbindung prüfen')
        : 'Noch keine Paketquelle eingerichtet';
    return [
      '<section class="panel"><h2>Cubi-Paketserver · Smartify Energy Pro</h2>',
      '<p class="notice">Lädt freigegebene SEP-Pakete nach Home Assistant. Lokaler LAN-Test per HTTP oder geschützter Zugriff per Tailscale HTTPS. Keine automatische Installation.</p>',
      '<div class="pinrow"><input id="kubi-url" style="max-width:310px;min-width:220px;flex:1" aria-label="Cubi Paketserver URL" placeholder="https://smartify-packages.tail8ff129.ts.net" autocomplete="off" spellcheck="false" value="'+escape(k.url||'')+'">',
      '<button id="kubi-save">Server speichern</button><button id="kubi-check">Jetzt auf Updates prüfen</button></div>',
      '<div class="notice" style="margin-top:12px">'+status+'</div>',
      k.connected&&k.update_available?'<p class="notice ok" role="status"><strong>SEP-Update verfügbar: '+escape(k.installed_version)+' → '+escape(k.version)+'</strong> · Auch unter Home Assistant → Einstellungen → Updates sichtbar.</p>':'',
      k.connected?'<div class="buttons" style="margin-top:12px"><button id="kubi-download" class="primary">Geprüftes ZIP nach Home Assistant laden</button></div><p class="notice">Ziel: /config/smartify-downloads/sep/ · Installierte SEP-Version unverändert.</p>':'',
      this._downloadInfo?'<p class="notice ok" role="status">Gespeichert: '+escape(this._downloadInfo.destination)+' (SEP '+escape(this._downloadInfo.version)+')</p>':'',
      '</section>'
    ].join('');
  }
  render() {
    const appIcon = app => {
      const path = SMARTIFY_ORIGINAL_ICONS[app.id];
      const fallback = SMARTIFY_FALLBACK_ICONS[app.id] || 'mdi:apps';
      const original = path
        ? `<img src="https://raw.githubusercontent.com/smartify-your-home/${path}" alt="" loading="lazy" decoding="async">`
        : '';
      return `${original}<ha-icon icon="${fallback}" ${path ? 'hidden' : ''}></ha-icon>`;
    };
    const escape = v => String(v ?? '').replace(/[&<>"']/g, ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
        .wrap{max-width:1100px;margin:auto;padding:24px 18px 48px}.head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
        h1{font-size:27px;letter-spacing:-.5px;margin:0}h2{font-size:17px;margin:0 0 12px}p{color:var(--secondary-text-color);margin:6px 0 0}.count{font-weight:700}
        .controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:22px}.panel{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,14px);padding:18px;margin-top:16px;box-shadow:var(--ha-card-box-shadow,none)}
        .apps-list{margin-top:12px;border-top:1px solid var(--divider-color)}
        .app-row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;align-items:center;column-gap:12px;row-gap:6px;padding:10px 2px;border-bottom:1px solid var(--divider-color);min-width:0}
        .app-icon{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:8px;background:var(--secondary-background-color);overflow:hidden;flex-shrink:0}
        .app-icon img{display:block;width:27px;height:27px;object-fit:contain;border-radius:5px}
        .app-icon img[hidden],.app-icon ha-icon[hidden]{display:none}
        .app-icon ha-icon{--mdc-icon-size:21px;color:var(--secondary-text-color)}
        .app-info{min-width:0}.name{font-size:14px;font-weight:650;line-height:1.35;overflow-wrap:anywhere}
        .meta{font-size:12px;color:var(--secondary-text-color);margin-top:2px;line-height:1.35;overflow-wrap:anywhere}
        .app-actions{display:flex;gap:6px;justify-content:flex-end;align-items:center;flex-wrap:wrap}
        .buttons{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
        @media (max-width:720px){.app-row{grid-template-columns:30px minmax(0,1fr);padding:10px 2px}.app-actions{grid-column:2;justify-content:flex-start}}
        .app-actions a.button,.app-actions button{font-size:12px;padding:6px 9px;white-space:nowrap}
        button,a.button{font:inherit;font-size:13px;border:1px solid var(--divider-color);border-radius:var(--ha-card-border-radius,8px);padding:9px 12px;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer;text-decoration:none}
        button.primary{background:var(--primary-color);border-color:var(--primary-color);color:var(--text-primary-color,#fff)}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
        input{background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color);padding:10px;border-radius:8px;max-width:230px}.tag{font-size:11px;border:1px solid var(--divider-color);border-radius:20px;padding:3px 8px;display:inline-block}.warn{color:var(--error-color)}.ok{color:var(--success-color,var(--primary-color))}.notice{font-size:13px;line-height:1.5}.pinrow{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:12px}
      </style>
      <main class="wrap">
        <div class="head"><div><h1>Smartify App Manager</h1><p>Zentrale Übersicht deiner Smartify-Erweiterungen</p></div><span class="tag">v0.3.0 · ohne Testzeitraum</span></div>
        <div class="controls"><span class="count">${this._apps.length} Module im Katalog</span><button id="refresh">App-Katalog aktualisieren</button></div>
        <p class="notice">Automatische Synchronisierung alle 6 Stunden · Letzter Abgleich: ${this._lastSynced?escape(new Date(this._lastSynced).toLocaleString('de-AT')):'noch keiner'} · manueller Abgleich frühestens alle 10 Minuten</p>
        ${this._syncError?`<p class="warn" role="status">${escape(this._syncError)}</p>`:''}
        ${this._error?`<p class="warn" role="alert">${escape(this._error)}</p>`:''}${this._success?`<p class="ok" role="status">${escape(this._success)}</p>`:''}
        <section class="panel"><h2>Smartify Apps</h2><div class="notice">Installation und Updates erfolgen über Home Assistant / HACS. Hier kannst du das jeweilige Repository öffnen. „Sperren“ ist derzeit nur ein Verwaltungskennzeichen und <strong>deaktiviert keine laufende Integration</strong>.</div>
          <div class="apps-list" role="list">${this._apps.map(app=>`<article class="app-row" role="listitem"><span class="app-icon" aria-hidden="true">${appIcon(app)}</span><div class="app-info"><div class="name">${escape(app.name)}</div><div class="meta">${escape(app.category)} · ${app.latest_version?`GitHub: ${escape(app.latest_version)} · `:""}${app.new?"Neu entdeckt · ":""}${app.locked?'🔒 Gesperrt (Kennzeichen)':'Verfügbar'}</div></div><div class="app-actions"><a class="button" href="${escape(app.url)}" target="_blank" rel="noopener noreferrer" aria-label="Repository für ${escape(app.name)} öffnen">Repository ↗</a>${app.release_url?`<a class="button" href="${escape(app.release_url)}" target="_blank" rel="noopener noreferrer">Release Notes ↗</a>`:""}<button data-id="${escape(app.id)}" data-locked="${app.locked?'false':'true'}">${app.locked?'Entsperren':'Sperren'}</button></div></article>`).join('')}</div>
        </section>
        ${this.kubiPanel(escape)}
        <section class="panel"><h2>Administrator-PIN</h2><p class="notice">Mindestens 6 Zeichen. PIN schützt die Änderung der Modul-Kennzeichen. Die Anmeldung als HA-Administrator ist zusätzlich erforderlich.</p><div class="pinrow">${this._pinConfigured?'<input type="password" id="old" placeholder="Bisherige PIN" autocomplete="off">':''}<input type="password" id="new" placeholder="Neue PIN (mind. 6)" autocomplete="new-password"><button id="setpin">${this._pinConfigured?'PIN ändern':'PIN einrichten'}</button></div></section>
      </main>`;
    this.shadowRoot.querySelector('#refresh').onclick=()=>this.manualRefresh();
    this.shadowRoot.querySelector('#setpin').onclick=()=>this.setPin();
    this.shadowRoot.querySelector('#kubi-save').onclick=()=>this.saveKubiUrl();
    this.shadowRoot.querySelector('#kubi-check').onclick=()=>this.checkKubi();
    const kubiDownload=this.shadowRoot.querySelector('#kubi-download');
    if(kubiDownload)kubiDownload.onclick=()=>this.downloadKubi();
    this.shadowRoot.querySelectorAll('.app-icon img').forEach(img => {
      img.addEventListener('error', () => {
        img.hidden = true;
        const fallback = img.parentElement.querySelector('ha-icon');
        if (fallback) fallback.hidden = false;
      }, {once:true});
    });
    this.shadowRoot.querySelectorAll('button[data-id]').forEach(button=>button.onclick=()=>this.setLock(button.dataset.id,button.dataset.locked==='true'));
  }
  async manualRefresh() {
    try {
      const result = await this._hass.callWS({type:'smartify_app_manager/refresh'});
      this._success = result.updated ? 'App-Katalog aktualisiert (derzeit GitHub-Übergangsquelle).' : 'Kein neuer Katalogabgleich (10-Minuten-Sperre oder GitHub nicht erreichbar).';
      this._error = '';
    } catch(err) {
      this._error = String(err.message || err);
    }
    await this.refresh();
  }
  async saveKubiUrl(){
    const url=this.shadowRoot.querySelector('#kubi-url').value.trim();
    try {
      const result=await this._hass.callWS({type:'smartify_app_manager/kubi_set_url',url});
      this._kubi={configured:!!result.url,connected:false,url:result.url};
      this._downloadInfo=null;
      this._success=result.url?'Cubi-Paketquelle gespeichert.':'Cubi-Paketquelle deaktiviert.';
      this._error='';
      await this.checkKubi();
    } catch(err) {
      this._error=String(err.message||err);
      this.render();
    }
  }
  async downloadKubi(){
    if(!this._kubi.connected || this._busy)return;
    this._busy=true;
    this._downloadInfo=null;
    this._error='';
    this._success='SEP-Paket wird heruntergeladen und geprüft…';
    this.render();
    try {
      const result=await this._hass.callWS({type:'smartify_app_manager/kubi_download'});
      this._downloadInfo=result;
      this._success='SEP-Paket geprüft und lokal in Home Assistant gespeichert.';
      this._error='';
    } catch(err) {
      this._success='';
      this._error=String(err.message||err);
    } finally {
      this._busy=false;
      this.render();
    }
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
