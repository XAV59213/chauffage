/* Carte Lovelace « Chauffage Fil Pilote » — livrée avec l'intégration electric_heater.
 *
 * Utilisation : type: custom:electric-heater-card
 * Aucune option obligatoire : la carte trouve toute seule le thermostat central,
 * tous les radiateurs ajoutés et les capteurs résumé de l'intégration.
 * Options (fallback) : central, radiateurs (liste), fenetres, sondes_ko, alerte_pile,
 * presents, titre.
 */
const CARD_TAG = "electric-heater-card";
const DOMAIN = "electric_heater";

const ORDRES = {
  comfort: "Confort",
  "comfort_-1": "Confort -1",
  "comfort_-2": "Confort -2",
  eco: "Eco",
  frost_protection: "Hors-gel",
  off: "Arrêt",
};
const HVAC = { auto: "Auto", heat: "Chauffage", off: "Éteint" };

function _esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function _num(v, d = 1) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(d) : "–";
}

/* Entités de l'intégration : registre (platform) puis repli sur les attributs. */
function _discover(hass) {
  const states = hass.states || {};
  const reg = hass.entities || {};
  const ours = Object.keys(states).filter(
    (id) => (reg[id] && reg[id].platform === DOMAIN) || id.startsWith("climate.electric_heater")
  );
  const pool = ours.length ? ours : Object.keys(states);
  const attrs = (id) => (states[id] && states[id].attributes) || {};
  const climates = pool.filter((id) => id.startsWith("climate."));

  const central =
    climates.find((id) => id === "climate.electric_heater_central") ||
    climates.find((id) => "base_preset" in attrs(id) && "temperatures" in attrs(id)) ||
    "";
  const radiateurs = climates
    .filter((id) => id !== central && ("fil_pilote_ordre" in attrs(id) || "follow_central" in attrs(id)))
    .sort((a, b) => _name(hass, a).localeCompare(_name(hass, b), "fr"));
  const sensors = pool.filter((id) => id.startsWith("sensor."));
  const bins = pool.filter((id) => id.startsWith("binary_sensor."));
  return {
    central,
    radiateurs,
    fenetres:
      sensors.find((id) => id.endsWith("fenetres_ouvertes")) ||
      sensors.find((id) => "fenetres" in attrs(id) && "entites" in attrs(id)) ||
      "",
    sondes_ko:
      sensors.find((id) => id.endsWith("sondes_ko")) ||
      sensors.find((id) => "sondes" in attrs(id) && "liste" in attrs(id)) ||
      "",
    alerte_pile:
      bins.find((id) => id.includes("alerte_pile")) ||
      bins.find((id) => "sondes" in attrs(id) && attrs(id).device_class === "problem") ||
      "",
    presents:
      sensors.find((id) => id.endsWith("_presents")) ||
      sensors.find((id) => "source" in attrs(id) && "count" in attrs(id)) ||
      "",
  };
}

function _name(hass, id) {
  const st = hass.states[id];
  return (st && st.attributes.friendly_name) || id;
}

const STYLES = `
  ha-card { padding: 16px; }
  .head { display:flex; align-items:center; justify-content:space-between; gap:12px; }
  .title { font-size: 1.2em; font-weight: 600; }
  .big { font-size: 2.2em; font-weight: 300; line-height: 1; }
  .muted { color: var(--secondary-text-color); font-size: .9em; }
  .chips { display:flex; flex-wrap:wrap; gap:8px; margin:14px 0 6px; }
  .chip { display:flex; align-items:center; gap:6px; padding:6px 10px; border-radius:16px;
          background: var(--secondary-background-color); cursor:pointer; font-size:.9em; }
  .chip.warn { background: rgba(255,152,0,.18); color: var(--warning-color, #ff9800); }
  .chip.bad { background: rgba(244,67,54,.15); color: var(--error-color, #f44336); }
  .chip ha-icon { --mdc-icon-size: 18px; }
  .alert { margin:8px 0; padding:8px 10px; border-radius:8px; font-size:.9em;
           background: rgba(244,67,54,.12); color: var(--error-color, #f44336); }
  .rows { margin-top: 10px; }
  .row { display:flex; align-items:center; gap:10px; padding:8px 0; cursor:pointer;
         border-top: 1px solid var(--divider-color); }
  .row .n { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .row .t { min-width: 64px; text-align:right; }
  .badge { font-size:.8em; padding:2px 8px; border-radius:10px; background: var(--secondary-background-color); }
  .badge.heat { background: rgba(255,87,34,.2); color: #ff5722; }
  .badge.ko { background: rgba(244,67,54,.15); color: var(--error-color, #f44336); }
  .empty { padding: 8px 0; }
`;

class ElectricHeaterCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  static getStubConfig() {
    return {};
  }

  getCardSize() {
    return 3 + ((this._ents && this._ents.radiateurs.length) || 0);
  }

  set hass(hass) {
    this._hass = hass;
    const auto = _discover(hass);
    const c = this._config || {};
    this._ents = {
      central: c.central || auto.central,
      radiateurs: Array.isArray(c.radiateurs) && c.radiateurs.length ? c.radiateurs : auto.radiateurs,
      fenetres: c.fenetres || auto.fenetres,
      sondes_ko: c.sondes_ko || auto.sondes_ko,
      alerte_pile: c.alerte_pile || auto.alerte_pile,
      presents: c.presents || auto.presents,
    };
    const ids = [this._ents.central, this._ents.fenetres, this._ents.sondes_ko, this._ents.alerte_pile,
      this._ents.presents, ...this._ents.radiateurs];
    const sig = ids.map((id) => {
      const s = hass.states[id];
      return s ? `${id}|${s.last_updated}` : id;
    }).join(";");
    if (sig === this._sig) return;
    this._sig = sig;
    this._render();
  }

  _more(id) {
    if (!id) return;
    const ev = new Event("hass-more-info", { bubbles: true, composed: true });
    ev.detail = { entityId: id };
    this.dispatchEvent(ev);
  }

  _render() {
    const hass = this._hass;
    const e = this._ents;
    const st = (id) => (id && hass.states[id]) || null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });

    const central = st(e.central);
    const titre = this._config.titre || (central && central.attributes.friendly_name) || "Chauffage";
    let head;
    if (central) {
      const a = central.attributes;
      const action = a.hvac_action === "heating" ? "Chauffe" : a.hvac_action === "off" ? "Arrêt" : "Inactif";
      head = `
        <div class="head" data-id="${_esc(e.central)}">
          <div>
            <div class="title">${_esc(titre)}</div>
            <div class="muted">${_esc(HVAC[central.state] || central.state)} · ${_esc(ORDRES[a.preset_mode] || a.preset_mode || "")} · ${_esc(action)}</div>
          </div>
          <div style="text-align:right">
            <div class="big">${_num(a.current_temperature)}°</div>
            <div class="muted">consigne ${_num(a.temperature)}°</div>
          </div>
        </div>`;
    } else {
      head = `<div class="title">${_esc(titre)}</div>
        <div class="muted empty">Thermostat central introuvable : ajoutez l'intégration « Chauffage Electrique Fil Pilote FR ».</div>`;
    }

    const chips = [];
    const fen = st(e.fenetres);
    if (fen) {
      const n = Number(fen.state) || 0;
      chips.push(`<div class="chip ${n ? "warn" : ""}" data-id="${_esc(e.fenetres)}">
        <ha-icon icon="${n ? "mdi:window-open-variant" : "mdi:window-closed-variant"}"></ha-icon>
        ${n ? `${n} fenêtre${n > 1 ? "s" : ""} ouverte${n > 1 ? "s" : ""}` : "Fenêtres fermées"}</div>`);
    }
    const ko = st(e.sondes_ko);
    const pile = st(e.alerte_pile);
    const nko = ko ? Number(ko.state) || 0 : pile && pile.state === "on" ? 1 : 0;
    if (ko || pile) {
      chips.push(`<div class="chip ${nko ? "bad" : ""}" data-id="${_esc(e.alerte_pile || e.sondes_ko)}">
        <ha-icon icon="${nko ? "mdi:battery-alert-variant-outline" : "mdi:battery-check"}"></ha-icon>
        ${nko ? `${nko} sonde${nko > 1 ? "s" : ""} KO` : "Sondes OK"}</div>`);
    }
    const pres = st(e.presents);
    if (pres) {
      chips.push(`<div class="chip" data-id="${_esc(e.presents)}">
        <ha-icon icon="${_esc(pres.attributes.icon || "mdi:account-group")}"></ha-icon>${_esc(pres.state)}</div>`);
    }

    let alerts = "";
    if (fen && Number(fen.state) > 0) {
      const l = fen.attributes.fenetres || [];
      alerts += `<div class="alert" style="background:rgba(255,152,0,.15);color:var(--warning-color,#ff9800)">
        🪟 Ouvertes : ${_esc(l.join(", "))}</div>`;
    }
    if (nko) {
      const src = (pile && pile.attributes.pieces) || (ko && ko.attributes.pieces) || [];
      alerts += `<div class="alert">🔋 Remplacer la pile de la sonde : ${_esc(src.join(", "))}
        <br><span class="muted">Radiateurs concernés en Hors-gel par sécurité.</span></div>`;
    }

    const rows = e.radiateurs.map((id) => {
      const s = st(id);
      if (!s) return "";
      const a = s.attributes;
      const ordre = a.fil_pilote_ordre || a.preset_mode;
      const heat = a.hvac_action === "heating";
      const badge = a.sonde_ko
        ? `<span class="badge ko">Sonde KO</span>`
        : `<span class="badge ${heat ? "heat" : ""}">${_esc(ORDRES[ordre] || ordre || "–")}</span>`;
      const win = a.window_open ? ` <ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size:16px"></ha-icon>` : "";
      return `<div class="row" data-id="${_esc(id)}">
        <ha-icon icon="${heat ? "mdi:radiator" : "mdi:radiator-disabled"}"></ha-icon>
        <div class="n">${_esc(a.friendly_name || id)}${win}</div>
        ${badge}
        <div class="t">${_num(a.current_temperature)}° <span class="muted">/ ${_num(a.temperature)}°</span></div>
      </div>`;
    }).join("");

    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
      <ha-card>
        ${head}
        <div class="chips">${chips.join("")}</div>
        ${alerts}
        <div class="rows">${rows || `<div class="muted empty">Aucun radiateur trouvé.</div>`}</div>
      </ha-card>`;
    this.shadowRoot.querySelectorAll("[data-id]").forEach((el) =>
      el.addEventListener("click", () => this._more(el.getAttribute("data-id")))
    );
  }
}

if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, ElectricHeaterCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Chauffage Fil Pilote",
    description: "Thermostat central, fenêtres ouvertes, sondes KO / piles, présents et radiateurs (découverte automatique)",
    preview: true,
    documentationURL: "https://github.com/XAV59213/chauffage/tree/main/examples/lovelace",
  });
}
