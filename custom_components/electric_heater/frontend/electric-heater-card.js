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
function _statsFor(hass, id) {
  const reg = hass.entities || {};
  const dev = reg[id] && reg[id].device_id;
  const ids = dev
    ? Object.keys(reg).filter((x) => reg[x].device_id === dev && x.startsWith("sensor."))
    : Object.keys(hass.states).filter((x) => x.startsWith("sensor.") && x.includes("maison"));
  const val = (x) => {
    const s = x && hass.states[x];
    const n = s ? Number(s.state) : NaN;
    return Number.isFinite(n) ? n : null;
  };
  const h = ids.filter((x) => x.includes("temps_de_chauffe") && x.includes("aujourd")).map(val)[0];
  const kwh = ids.filter((x) => x.includes("consommation") && x.includes("aujourd") && !x.includes("compteur")).map(val)[0];
  const meterDay = ids.filter((x) => x.includes("compteur") && x.includes("aujourd")).map(val)[0];
  // Compteur réel (sensor.*_energy) lié au radiateur ou somme centrale.
  let meter = null;
  const linked = hass.states[id] && hass.states[id].attributes.energy_sensor;
  const meterId = linked || ids.find((x) => x.includes("conso_compteurs") || x.includes("consommation_radiateurs"));
  if (meterId && hass.states[meterId]) {
    const ms = hass.states[meterId];
    const n = Number(ms.state);
    if (Number.isFinite(n)) meter = ms.attributes.unit_of_measurement === "Wh" ? n / 1000 : n;
  }
  return { h: h ?? null, kwh: kwh ?? null, meter, meterDay: meterDay ?? null };
}

function _fmtStats(st) {
  const parts = [];
  if (st.h !== null) {
    const m = Math.round(st.h * 60);
    parts.push(`⏱ ${m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`}`);
  }
  if (st.meterDay !== null && st.meterDay !== undefined) parts.push(`🔌 ${st.meterDay.toFixed(2)} kWh`);
  else if (st.kwh) parts.push(`⚡ ${st.kwh.toFixed(2)} kWh`);
  return parts.join(" · ");
}

function _fmtMeter(st) {
  return st.meter !== null && st.meter !== undefined ? `🔌 ${st.meter.toFixed(1)} kWh compteur` : "";
}

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
    etat_fenetres:
      sensors.find((id) => "windows" in attrs(id) && "sources" in attrs(id) && id.includes("central")) ||
      sensors.find((id) => "windows" in attrs(id) && "sources" in attrs(id)) ||
      "",
    presents:
      sensors.find((id) => id.endsWith("_presents")) ||
      sensors.find((id) => "source" in attrs(id) && "count" in attrs(id)) ||
      "",
  };
}

/* Personnes à la maison : person.* « home » (friendly_name), sinon attribut du capteur Présents. */
const NON_PERSONNES = ["tablette", "tablet", "ipad", "iphone", "android", "telephone", "téléphone",
  "phone", "mqtt", "mqtta", "maison", "home", "tv", "television", "pc", "ordinateur", "macbook", "laptop",
  "chromecast", "alexa", "echo", "box", "freebox", "serveur", "server", "voiture", "car", "koleos"];
// Indices forts : reconnus même collés au nom (ipadpapa, tablettep, iphonexav...).
const APPAREILS = ["tablette", "tablet", "ipad", "iphone", "android", "mqtt", "telephone", "téléphone",
  "smartphone", "galaxy", "pixel", "macbook", "laptop", "chromecast", "freebox"];
function _isDevice(text, skip) {
  const t = String(text).toLowerCase();
  const words = t.split(/[^0-9a-zà-ÿ]+/).filter(Boolean);
  return words.some((w) => skip.includes(w)) || skip.includes(t) || APPAREILS.some((a) => t.includes(a));
}
function _presentNames(hass, pres, exclure = []) {
  const skip = [...NON_PERSONNES, ...exclure.map((x) => String(x).toLowerCase())];
  // Priorité au capteur Présents (personnes choisies dans la config de l'intégration).
  if (pres && Array.isArray(pres.attributes.personnes)) {
    const chosen = Array.isArray(pres.attributes.personnes_suivies);
    return pres.attributes.personnes
      .filter((n) => (chosen ? !skip.includes(String(n).toLowerCase()) : !_isDevice(n, skip)))
      .map((n) => {
        const id = Object.keys(hass.states).find((k) => k.startsWith("person.") && _name(hass, k) === n);
        return { id: id || pres.entity_id, name: n };
      });
  }
  const list = Object.keys(hass.states)
    .filter((id) => id.startsWith("person.") && hass.states[id].state === "home")
    .filter((id) => !_isDevice(id.slice(7), skip) && !_isDevice(_name(hass, id), skip))
    .map((id) => ({ id, name: _name(hass, id) }))
    .sort((a, b) => a.name.localeCompare(b.name, "fr"));
  if (list.length) return list;
  const attr = (pres && pres.attributes.personnes) || [];
  return attr.filter((n) => !skip.includes(String(n).toLowerCase())).map((n) => ({ id: pres.entity_id, name: n }));
}

/* Piles des détecteurs de fenêtre : capteur batterie du même appareil (registre HA). */
const PILE_FAIBLE = 20;
function _batteryFor(hass, eid) {
  const reg = hass.entities || {};
  const dev = reg[eid] && reg[eid].device_id;
  let pct = null;
  let low = null;
  let src = null;
  const take = (id) => {
    const st = hass.states[id];
    if (!st) return;
    if (id.startsWith("binary_sensor.")) {
      if (low === null) { low = st.state === "on"; src = src || id; }
    } else {
      const n = Number(st.state);
      if (Number.isFinite(n) && pct === null) { pct = n; src = id; }
    }
  };
  if (dev) {
    for (const id of Object.keys(reg)) {
      if (reg[id].device_id !== dev || id === eid) continue;
      const st = hass.states[id];
      if (st && (st.attributes.device_class === "battery" || /_(battery|batterie)(_low)?$/.test(id))) take(id);
    }
  }
  if (pct === null && low === null) {
    // Repli par nom : sensor.<base>_battery (Zigbee2MQTT / ZHA sans registre d'appareil).
    const base = eid.split(".")[1].replace(/_(contact|ouverture|opening|window|door|porte|fenetre|temperature|temp|humidity|humidite)$/, "");
    for (const id of [`sensor.${base}_battery`, `sensor.${base}_batterie`, `binary_sensor.${base}_battery_low`]) take(id);
  }
  const st = hass.states[eid];
  const attrPct = st && Number(st.attributes.battery);
  if (pct === null && Number.isFinite(attrPct)) { pct = attrPct; src = eid; }
  return { id: src || eid, eid, name: _name(hass, eid), pct, low: low === true || (pct !== null && pct <= PILE_FAIBLE),
    unknown: pct === null && low === null };
}

const OUVERT = ["on", "open", "opened", "opening", "true", "1", "ouvert", "ouverte"];
const FERME = ["off", "closed", "closing", "false", "0", "ferme", "fermé", "fermee", "fermée"];
const _WIN_LAST = {};
const _WIN_GRACE = 15 * 60 * 1000;
function _windowState(hass, eid) {
  const st = hass.states[eid];
  if (!st || ["unknown", "unavailable"].includes(st.state)) {
    const l = _WIN_LAST[eid];
    return l && Date.now() - l.t <= _WIN_GRACE ? l.v + "_perdu" : "indispo";
  }
  const v0 = _windowStateRaw(st);
  if (v0 !== "indispo") _WIN_LAST[eid] = { v: v0, t: Date.now() };
  return v0;
}
function _windowStateRaw(st) {
  const v = String(st.state).toLowerCase();
  if (OUVERT.includes(v)) return "ouvert";
  if (FERME.includes(v)) return "ferme";
  if (typeof st.attributes.contact === "boolean") return st.attributes.contact ? "ferme" : "ouvert";
  return "indispo";
}

function _base(eid) {
  return eid.split(".")[1]
    .replace(/_(contact|ouverture|opening|window|door|porte|fenetre|temperature|temp|humidity|humidite|battery|batterie|battery_low)$/, "")
    .replace(/_\d+$/, "");
}

function _batteries(hass, ids) {
  const reg = hass.entities || {};
  const rows = [];
  const seen = new Set();
  for (const id of [...new Set(ids.filter(Boolean).map((x) => String(x).trim()))]) {
    // Entité inexistante (ancien entity_id) : ignorée, le vrai détecteur est déjà listé.
    if (!hass.states[id]) continue;
    const row = _batteryFor(hass, id);
    const dev = reg[id] && reg[id].device_id;
    row.keys = [dev && `dev:${dev}`, !row.unknown && `bat:${row.id}`].filter(Boolean);
    if (!row.unknown && row.keys.some((k) => k.startsWith("bat:") && seen.has(k))) continue;
    if (!row.unknown) row.keys.forEach((k) => seen.add(k));
    rows.push(row);
  }
  // « Pile ? » masqué si le même détecteur (appareil ou nom de base) a déjà un %.
  // Dédup prudente : même appareil / même capteur batterie, ou même nom une fois
  // retirés « detecteur », « capteur » et les suffixes techniques (baie_vitree = Détecteur baie vitrée).
  const norm = (t) => String(t).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_").replace(/^(detecteur|capteur|sensor)_/, "")
    .replace(/_(contact|ouverture|opening|\d+)$/, "").replace(/^_+|_+$/g, "");
  const knownNames = new Set(rows.filter((r) => !r.unknown).flatMap((r) => [norm(r.name), norm(r.eid.split(".")[1])]));
  const out = rows.filter((r) => !r.unknown
    || (!r.keys.some((k) => k.startsWith("dev:") && seen.has(k))
        && !knownNames.has(norm(r.name)) && !knownNames.has(norm(r.eid.split(".")[1]))));
  const uniq = [];
  const done = new Set();
  for (const r of out) {
    const k = r.keys.find((x) => x.startsWith("dev:")) || `eid:${r.eid}`;
    if (done.has(k)) continue;
    done.add(k);
    uniq.push(r);
  }
  return uniq.sort((a, b) => (b.low - a.low) || (a.unknown - b.unknown) || a.name.localeCompare(b.name, "fr"));
}

function _windowBatteries(hass, winIds) {
  return _batteries(hass, winIds);
}

function _name(hass, id) {
  const st = hass.states[id];
  return (st && st.attributes.friendly_name) || id;
}

const GRAPH_COLORS = ["#ff7043", "#42a5f5", "#66bb6a", "#ab47bc", "#ffca28", "#26c6da", "#ec407a", "#8d6e63"];

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
  .chip.ok { background: rgba(76,175,80,.18); color: var(--success-color, #4caf50); }
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
      etat_fenetres: c.etat_fenetres || auto.etat_fenetres,
    };
    const allWin = new Set();
    for (const id of Object.keys(hass.states)) {
      const a = hass.states[id].attributes;
      if (id.startsWith("sensor.") && Array.isArray(a.windows) && a.sources) {
        a.windows
          .filter((w) => typeof w === "string" && /^(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+$/.test(w.trim()))
          .forEach((w) => allWin.add(w.trim()));
      }
    }
    // Détecteurs configurés sur chaque radiateur (Configurer) : toujours listés.
    for (const rid of this._ents.radiateurs) {
      const ws = hass.states[rid] && hass.states[rid].attributes.window_sensors;
      if (Array.isArray(ws)) {
        ws.filter((w) => typeof w === "string" && /^(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+$/.test(w.trim()))
          .forEach((w) => allWin.add(w.trim()));
      }
    }
    // + détecteurs fenêtre / porte de la même pièce (zone HA) que chaque radiateur ou le central.
    const reg = hass.entities || {};
    const devs = hass.devices || {};
    const areaOf = (id) => {
      const e = reg[id];
      if (!e) return null;
      return e.area_id || (e.device_id && devs[e.device_id] && devs[e.device_id].area_id) || null;
    };
    const areas = new Set([...this._ents.radiateurs, this._ents.central].map(areaOf).filter(Boolean));
    const WIN_CLASSES = ["window", "door", "opening", "garage_door"];
    if (areas.size) {
      for (const id of Object.keys(hass.states)) {
        if (!id.startsWith("binary_sensor.")) continue;
        const st = hass.states[id];
        const dc = st.attributes.device_class;
        const hint = `${id} ${st.attributes.friendly_name || ""}`.toLowerCase();
        if ((reg[id] && reg[id].platform === DOMAIN) || /batter|_low|tamper|problem|update|connect|securit|alarm|vibration/.test(hint)) continue;
        if (dc && !WIN_CLASSES.includes(dc)) continue;
        const isWin = WIN_CLASSES.includes(dc) || /fen[eê]tre|window|baie|porte/.test(hint);
        if (isWin && areas.has(areaOf(id))) allWin.add(id);
      }
    }
    // + détecteurs dont le nom contient la pièce d'un radiateur (ex. « salon »), même hors zone.
    const roomWords = new Set();
    for (const a of areas) {
      const n = hass.areas && hass.areas[a] && hass.areas[a].name;
      if (n) roomWords.add(n.toLowerCase().trim());
    }
    for (const rid of this._ents.radiateurs) {
      const n = _name(hass, rid).toLowerCase();
      for (const w of ["salon", "sejour", "séjour", "cuisine", "entree", "entrée", "bureau", "salle a manger", "salle à manger"]) {
        if (n.includes(w)) roomWords.add(w);
      }
    }
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith("binary_sensor.") || allWin.has(id)) continue;
      const st = hass.states[id];
      const dc = st.attributes.device_class;
      const hint = `${id} ${st.attributes.friendly_name || ""}`.toLowerCase();
      if ((reg[id] && reg[id].platform === DOMAIN) || /batter|_low|tamper|problem|update|connect|securit|alarm|vibration|motion|mouvement|occupancy|presence/.test(hint)) continue;
      const winLike = WIN_CLASSES.includes(dc) || (!dc && /fen[eê]tre|window|baie|porte|ouverture|contact/.test(hint));
      if (winLike && [...roomWords].some((w) => w.length >= 4 && hint.includes(w))) allWin.add(id);
    }
    this._areaName = (id) => {
      const a = areaOf(id);
      return (a && hass.areas && hass.areas[a] && hass.areas[a].name) || "";
    };
    this._ents.detecteurs = Array.isArray(c.detecteurs_fenetre) && c.detecteurs_fenetre.length
      ? c.detecteurs_fenetre
      : [...allWin];
    this._ents.sondes = Array.isArray(c.sondes) && c.sondes.length
      ? c.sondes
      : this._ents.radiateurs
          .map((id) => hass.states[id] && hass.states[id].attributes.temperature_sensor)
          .filter(Boolean);
    const bats = [...this._ents.detecteurs, ...this._ents.sondes].flatMap((w) => {
      const dev = (hass.entities || {})[w] && hass.entities[w].device_id;
      return dev ? Object.keys(hass.entities).filter((id) => hass.entities[id].device_id === dev) : [w];
    });
    const statIds = Object.keys(hass.states).filter((x) => x.startsWith("sensor.") && (x.includes("temps_de_chauffe") || x.includes("consommation") || x.includes("conso") || x.endsWith("_energy")) || x.includes("calendrier_chauffage"));
    const ids = [...bats, ...statIds, this._ents.central, this._ents.fenetres, this._ents.sondes_ko, this._ents.alerte_pile,
      this._ents.presents, ...this._ents.radiateurs];
    const sig = ids.map((id) => {
      const s = hass.states[id];
      return s ? `${id}|${s.last_updated}` : id;
    }).join(";") + "#" + Object.keys(hass.states)
      .filter((id) => id.startsWith("person.") && hass.states[id].state === "home").join(",");
    this._loadHistory();
    if (sig === this._sig) return;
    this._sig = sig;
    this._render();
  }

  async _loadHistory() {
    const hass = this._hass;
    const c = this._config || {};
    if (!hass || c.graphique === false || !this._ents) return;
    const now = Date.now();
    if (this._histAt && now - this._histAt < 10 * 60 * 1000) return;
    this._histAt = now;
    const series = this._ents.radiateurs
      .map((rid) => ({ rid, sensor: hass.states[rid] && hass.states[rid].attributes.temperature_sensor }))
      .filter((x) => x.sensor);
    if (!series.length) return;
    const heures = Number(c.heures) || 24;
    const start = new Date(now - heures * 3600 * 1000).toISOString();
    const ids = series.map((x) => x.sensor).join(",");
    try {
      const res = await hass.callApi(
        "GET",
        `history/period/${start}?filter_entity_id=${ids}&end_time=${new Date(now).toISOString()}&minimal_response&no_attributes`
      );
      const byId = {};
      (res || []).forEach((arr) => {
        if (!arr || !arr.length) return;
        const eid = arr[0].entity_id;
        byId[eid] = arr
          .map((p) => [Date.parse(p.last_changed || p.lu * 1000), Number(p.state !== undefined ? p.state : p.s)])
          .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
      });
      this._hist = {
        start: now - heures * 3600 * 1000,
        end: now,
        series: series.map((x, i) => ({
          name: _name(hass, x.rid).replace(/^Radiateur\s*/i, "").replace(/\s*Chauffage.*$/i, ""),
          color: GRAPH_COLORS[i % GRAPH_COLORS.length],
          pts: byId[x.sensor] || [],
        })),
      };
      this._sig = null;
      this._render();
    } catch (err) {
      this._histAt = 0;
    }
  }

  _graph() {
    const h = this._hist;
    if (!h || !h.series.some((s) => s.pts.length)) return "";
    const W = 320, H = 140, L = 28, B = 16;
    const all = h.series.flatMap((s) => s.pts.map((p) => p[1]));
    let min = Math.floor(Math.min(...all)), max = Math.ceil(Math.max(...all));
    if (max - min < 2) { min -= 1; max += 1; }
    const x = (t) => L + ((t - h.start) / (h.end - h.start)) * (W - L - 4);
    const y = (v) => 4 + (1 - (v - min) / (max - min)) * (H - B - 4);
    const lines = h.series.filter((s) => s.pts.length).map((s) => {
      const pts = [...s.pts, [h.end, s.pts[s.pts.length - 1][1]]];
      let d = "";
      pts.forEach((p, i) => {
        const px = x(Math.max(p[0], h.start)).toFixed(1), py = y(p[1]).toFixed(1);
        d += i ? ` H${px} V${py}` : `M${px} ${py}`;
      });
      return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="1.6"/>`;
    }).join("");
    const grid = [min, (min + max) / 2, max].map((v) =>
      `<line x1="${L}" x2="${W - 4}" y1="${y(v)}" y2="${y(v)}" stroke="var(--divider-color,#555)" stroke-width="0.5"/>
       <text x="${L - 4}" y="${y(v) + 3}" font-size="9" text-anchor="end" fill="var(--secondary-text-color)">${Math.round(v * 10) / 10}°</text>`
    ).join("");
    const hrs = Math.round((h.end - h.start) / 3600000);
    const ticks = [0, 0.5, 1].map((f) => {
      const t = h.start + f * (h.end - h.start);
      const lab = f === 1 ? "maintenant" : new Date(t).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      return `<text x="${x(t)}" y="${H - 3}" font-size="9" text-anchor="${f === 0 ? "start" : f === 1 ? "end" : "middle"}" fill="var(--secondary-text-color)">${lab}</text>`;
    }).join("");
    const legend = h.series.map((s) =>
      `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px"><span style="width:10px;height:3px;background:${s.color};display:inline-block"></span>${_esc(s.name)}</span>`
    ).join("");
    return `<div class="rows"><div class="muted" style="margin-top:6px">Températures des pièces (${hrs} h)</div>
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">${grid}${lines}${ticks}</svg>
      <div class="muted" style="font-size:11px;line-height:1.8">${legend}</div></div>`;
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
    const ouvertsLive = (e.detecteurs || []).filter((d) => _windowState(hass, d) === "ouvert").length;
    if (fen || (e.detecteurs || []).length) {
      const n = Math.max(fen ? Number(fen.state) || 0 : 0, ouvertsLive);
      chips.push(`<div class="chip ${n ? "warn" : ""}" data-id="${_esc(e.fenetres || (e.detecteurs || [])[0] || "")}">
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
    const calId = (this._config || {}).calendrier ||
      Object.keys(hass.states).find((x) => x.startsWith("binary_sensor.") && x.includes("calendrier_chauffage_activ"));
    const cal = calId && hass.states[calId];
    if (cal) {
      const on = cal.state === "on";
      chips.push(`<div class="chip ${on ? "ok" : ""}" data-id="${_esc(calId)}">
        <ha-icon icon="${on ? "mdi:calendar-check" : "mdi:calendar-remove"}"></ha-icon>
        ${on ? "Calendrier chauffage actif" : "Calendrier chauffage inactif"}</div>`);
    }
    const pres = st(e.presents);
    if (pres) {
      chips.push(`<div class="chip" data-id="${_esc(e.presents)}">
        <ha-icon icon="${_esc(pres.attributes.icon || "mdi:account-group")}"></ha-icon>${_esc(pres.state)}</div>`);
    }
    const noms = _presentNames(hass, pres, this._config.exclure_personnes || []);
    if (noms.length) {
      chips.push(...noms.map((p) => `<div class="chip" data-id="${_esc(p.id)}">
        <ha-icon icon="mdi:account"></ha-icon>${_esc(p.name)}</div>`));
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

    const totS = _statsFor(hass, e.central);
    const tot = _fmtStats(totS);
    if (tot) chips.push(`<div class="chip">${tot} aujourd'hui</div>`);
    if (_fmtMeter(totS)) chips.push(`<div class="chip">${_fmtMeter(totS).replace("compteur", "total compteurs")}</div>`);

    const piles = _windowBatteries(hass, e.detecteurs || []);
    const pilesSondes = _batteries(hass, e.sondes || []);
    const faibles = [...piles, ...pilesSondes].filter((p) => p.low);
    if (piles.length || pilesSondes.length) {
      chips.push(`<div class="chip ${faibles.length ? "bad" : ""}" data-id="${_esc((faibles[0] || piles[0]).id)}">
        <ha-icon icon="${faibles.length ? "mdi:battery-alert" : "mdi:battery-high"}"></ha-icon>
        ${faibles.length ? `${faibles.length} pile${faibles.length > 1 ? "s" : ""} faible${faibles.length > 1 ? "s" : ""}` : "Piles OK"}</div>`);
    }
    const etat = (p) => {
      const w = _windowState(hass, p.eid);
      if (w === "ouvert") return `<span class="badge" style="background:rgba(255,152,0,.2);color:var(--warning-color,#ff9800)">🪟 Ouvert</span>`;
      if (w === "ferme") return `<span class="badge">Fermé</span>`;
      if (w === "ouvert_perdu") return `<span class="badge" title="Signal perdu, dernier état connu">🪟 Ouvert · 📶?</span>`;
      if (w === "ferme_perdu") return `<span class="badge" title="Signal perdu, dernier état connu">Fermé · 📶?</span>`;
      return `<span class="badge ko">Indisponible</span>`;
    };
    const winRow = (p) => `<div class="row" data-id="${_esc(p.eid)}">
        <ha-icon icon="${_windowState(hass, p.eid).startsWith("ouvert") ? "mdi:window-open-variant" : "mdi:window-closed-variant"}"></ha-icon>
        <div class="n">${_esc(p.name)}${this._areaName && this._areaName(p.eid) && !p.name.toLowerCase().includes(this._areaName(p.eid).toLowerCase()) ? ` <span class="muted">· ${_esc(this._areaName(p.eid))}</span>` : ""}</div>
        ${etat(p)}
        ${p.low ? `<span class="badge ko">Pile faible</span>` : p.unknown ? `<span class="badge">Pile ?</span>` : ""}
        <div class="t">${p.pct !== null ? `🔋 ${Math.round(p.pct)} %` : ""}</div>
      </div>`;
    const pileRow = (p) => `<div class="row" data-id="${_esc(p.id)}">
        <ha-icon icon="${p.low ? "mdi:battery-alert" : p.pct !== null && p.pct < 50 ? "mdi:battery-50" : "mdi:battery-high"}"></ha-icon>
        <div class="n">${_esc(p.name)}</div>
        ${p.low ? `<span class="badge ko">Pile faible</span>` : p.unknown ? `<span class="badge">Pile ?</span>` : `<span class="badge">OK</span>`}
        <div class="t">${p.pct !== null ? `${Math.round(p.pct)} %` : ""}</div>
      </div>`;
    const pileRows = piles.map(winRow).join("");
    const sondeRows = pilesSondes.map(pileRow).join("");

    const rows = e.radiateurs.map((id) => {
      const s = st(id);
      if (!s) return "";
      const a = s.attributes;
      const ordre = a.fil_pilote_ordre || a.preset_mode;
      const heat = a.hvac_action === "heating";
      const badge = a.sonde_ko
        ? `<span class="badge ko">Sonde KO</span>`
        : `<span class="badge ${heat ? "heat" : ""}">${_esc(ORDRES[ordre] || ordre || "–")}</span>`;
      const win = a.window_open || a.fenetre_detectee ? ` <ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size:16px"></ha-icon>` : "";
      return `<div class="row" data-id="${_esc(id)}">
        <ha-icon icon="${heat ? "mdi:radiator" : "mdi:radiator-disabled"}"></ha-icon>
        <div class="n">${_esc(a.friendly_name || id)}${win}${(() => { const x = _statsFor(hass, id); const t = [_fmtStats(x) && `${_fmtStats(x)} aujourd'hui`, _fmtMeter(x)].filter(Boolean).join(" · "); return t ? `<div class="muted" style="font-size:12px">${t}</div>` : ""; })()}</div>
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
        ${this._graph()}
        ${pileRows ? `<div class="rows"><div class="muted" style="margin-top:6px">Détecteurs de fenêtre (état et pile)</div>${pileRows}</div>` : ""}
        ${sondeRows ? `<div class="rows"><div class="muted" style="margin-top:6px">Piles des sondes de température</div>${sondeRows}</div>` : ""}
        ${(() => {
          const fmtH = (h) => { const m = Math.round((h || 0) * 60); return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`; };
          let totH = 0, totK = 0, anyK = false;
          const lines = e.radiateurs.map((id) => {
            const x = _statsFor(hass, id);
            if (x.h === null && x.kwh === null && x.meterDay === null) return "";
            totH += x.h || 0;
            const reel = x.meterDay !== null;
            const k = reel ? x.meterDay : x.kwh;
            if (k !== null) { totK += k; anyK = anyK || k > 0 || reel; }
            const nom = _name(hass, id).replace(/^Radiateur\s*/i, "").replace(/\s*Chauffage.*$/i, "");
            return `<div class="row" data-id="${_esc(id)}"><ha-icon icon="mdi:lightning-bolt"></ha-icon>
              <div class="n">${_esc(nom)}</div><span class="badge">${fmtH(x.h)}</span>
              <div class="t">${reel ? `🔌 ${k.toFixed(2)} kWh` : k !== null && k > 0 ? `≈ ${k.toFixed(2)} kWh` : "–"}</div></div>`;
          }).join("");
          if (!lines) return "";
          return `<div class="rows"><div class="muted" style="margin-top:6px">Consommation du jour par radiateur <span style="font-size:11px">(🔌 compteur réel · ≈ estimation)</span></div>${lines}
            <div class="row"><ha-icon icon="mdi:sigma"></ha-icon><div class="n"><b>Total</b></div>
              <span class="badge">${fmtH(totH)}</span><div class="t"><b>${anyK ? `${totK.toFixed(2)} kWh` : "–"}</b></div></div></div>`;
        })()}
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
