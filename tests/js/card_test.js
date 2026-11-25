/* Tests de la carte (node, sans dépendance) : découverte multi-bâtiments par le registre. */
"use strict";
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

/* DOM minimal : assez pour que la carte produise le HTML de ses blocs. */
class El {
  constructor() { this.children = []; this.dataset = {}; this.style = {}; this._html = ""; }
  set innerHTML(v) {
    this._html = v;
    this._ids = {};
    for (const m of v.matchAll(/id="([^"]+)"/g)) this._ids[m[1]] = new El();
    if (v.includes('class="eh-blocks"')) this._blocks = new El();
  }
  get innerHTML() { return this._html; }
  getElementById(i) { return this._ids[i]; }
  querySelector() { return this._blocks; }
  appendChild(c) { this.children.push(c); }
  addEventListener() {}
  remove() {}
}
class FakeHTMLElement extends El { attachShadow() { this.shadowRoot = new El(); return this.shadowRoot; } }

const src = fs.readFileSync(
  path.join(__dirname, "../../custom_components/electric_heater/frontend/electric-heater-card.js"), "utf8");
const defined = {};
const ctx = {
  HTMLElement: FakeHTMLElement,
  customElements: { get: (n) => defined[n], define: (n, c) => { defined[n] = c; } },
  window: {},
  document: { createElement: () => new El() },
  Date,
  setTimeout,
  clearTimeout,
  console,
  Event: class {},
  CustomEvent: class {},
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(src, ctx);
const Card = defined["electric-heater-card"];
const Editor = defined["electric-heater-card-editor"];

function st(attrs, state = "0") { return { state, attributes: attrs, last_updated: "t" }; }
const P = "electric_heater";

/* Deux bâtiments : Maison (historique) et Gîte ; un radiateur sans attribut (ancienne version) rattaché par appareil. */
function twoBuildings() {
  const states = {
    "climate.electric_heater_central": st({ friendly_name: "Thermostat virtuel", batiment: "Maison", central_entry_id: "BATA", base_preset: "eco", temperatures: {} }, "auto"),
    "climate.gite": st({ friendly_name: "Thermostat Gîte", batiment: "Gîte", central_entry_id: "BATB", base_preset: "eco", temperatures: {} }, "auto"),
    "climate.salon_chauffage_salon": st({ friendly_name: "Salon", central_entry_id: "BATA", fil_pilote_ordre: "eco" }),
    "climate.salon_chauffage_salon_2": st({ friendly_name: "Salon", central_entry_id: "BATB", fil_pilote_ordre: "eco" }),
    "climate.ancien": st({ friendly_name: "Ancien", fil_pilote_ordre: "eco" }),
    "sensor.x_fenetres_a": st({}, "1"),
    "sensor.y_fenetres_b": st({}, "0"),
    "sensor.total_conso": st({}, "3.5"),
    "sensor.total_h": st({}, "1.5"),
  };
  const entities = {
    "climate.electric_heater_central": { platform: P, device_id: "DA", translation_key: "central" },
    "climate.gite": { platform: P, device_id: "DB", translation_key: "central" },
    "climate.salon_chauffage_salon": { platform: P, device_id: "RA", translation_key: "room" },
    "climate.salon_chauffage_salon_2": { platform: P, device_id: "RB", translation_key: "room" },
    "climate.ancien": { platform: P, device_id: "RC", translation_key: "room" },
    "sensor.x_fenetres_a": { platform: P, device_id: "DA", translation_key: "fenetres_ouvertes" },
    "sensor.y_fenetres_b": { platform: P, device_id: "DB", translation_key: "fenetres_ouvertes" },
    "sensor.total_conso": { platform: P, device_id: "DA", translation_key: "global_conso_jour" },
    "sensor.total_h": { platform: P, device_id: "DA", translation_key: "global_chauffe_jour" },
  };
  const devices = { DA: {}, DB: {}, RA: { via_device_id: "DA" }, RB: { via_device_id: "DB" }, RC: { via_device_id: "DB" } };
  return { states, entities, devices, areas: {} };
}

const tests = {
  buildings_from_registry() {
    const hass = twoBuildings();
    const b = ctx._buildings(hass);
    assert.deepStrictEqual([...b.map((x) => x.name)], ["Gîte", "Maison"]);
    const gite = b[0];
    assert.strictEqual(gite.central, "climate.gite");
    // Par central_entry_id, sinon par appareil (via_device_id)
    assert.deepStrictEqual([...gite.radiateurs].sort(), ["climate.ancien", "climate.salon_chauffage_salon_2"]);
    assert.deepStrictEqual([...b[1].radiateurs], ["climate.salon_chauffage_salon"]);
    assert.strictEqual(ctx._discoverIn(hass, gite).fenetres, "sensor.y_fenetres_b");
    assert.strictEqual(ctx._discoverIn(hass, b[1]).fenetres, "sensor.x_fenetres_a");
  },
  pick_building() {
    const b = ctx._buildings(twoBuildings());
    assert.strictEqual(ctx._pickBuilding(b, "  gîte ").name, "Gîte");
    assert.strictEqual(ctx._pickBuilding(b, "BATA").name, "Maison");
    assert.strictEqual(ctx._pickBuilding(b, "climate.gite").name, "Gîte");
    assert.strictEqual(ctx._pickBuilding(b, "Inconnu"), null);
    assert.strictEqual(ctx._pickBuilding(b, ""), null);
  },
  global_totals() {
    const g = ctx._globalTotals(twoBuildings());
    assert.strictEqual(g.kwh, 3.5);
    assert.strictEqual(g.h, 1.5);
    assert.strictEqual(g.id, "sensor.total_conso");
  },
  card_tabs_and_pin() {
    const card = new Card();
    card._render = () => {};
    card.setConfig({});
    card.hass = twoBuildings();
    assert.strictEqual(card._tabs, true);
    assert.strictEqual(card._bld.name, "Gîte");
    assert.strictEqual(card._ents.central, "climate.gite");
    card._selectTab("BATA");
    assert.strictEqual(card._ents.central, "climate.electric_heater_central");
    assert.deepStrictEqual([...card._ents.radiateurs], ["climate.salon_chauffage_salon"]);
    // Bâtiment épinglé : pas d'onglets
    const pinned = new Card();
    pinned._render = () => {};
    pinned.setConfig({ batiment: "Maison" });
    pinned.hass = twoBuildings();
    assert.strictEqual(pinned._tabs, false);
    assert.strictEqual(pinned._bld.name, "Maison");
  },
  single_building_unchanged() {
    const hass = twoBuildings();
    for (const id of ["climate.gite", "climate.salon_chauffage_salon_2", "climate.ancien", "sensor.y_fenetres_b"]) {
      delete hass.states[id];
    }
    const card = new Card();
    card._render = () => {};
    card.setConfig({});
    card.hass = hass;
    assert.strictEqual(card._bld, null);
    assert.strictEqual(card._tabs, false);
    assert.strictEqual(card._ents.central, "climate.electric_heater_central");
    assert.deepStrictEqual([...card._ents.radiateurs], ["climate.salon_chauffage_salon"]);
    const ed = new Editor();
    ed._hass = hass;
    assert.ok(!ed._schema().some((f) => f.name === "batiment"));
  },
  editor_dropdown() {
    const ed = new Editor();
    ed._hass = twoBuildings();
    const f = ed._schema().find((x) => x.name === "batiment");
    assert.ok(f);
    assert.deepStrictEqual([...f.selector.select.options.map((o) => o.value)], ["", "Gîte", "Maison"]);
  },
};

function html(hass, conf = {}) {
  const card = new Card();
  card.setConfig(conf);
  card.hass = Object.assign(hass, { areas: {}, callApi: async () => [] });
  return card._blocksEl.children.map((x) => x.innerHTML).join("\n");
}

tests.render_multi_tabs_and_global_total = () => {
  const out = html(twoBuildings());
  assert.ok(out.includes('data-tab="BATB"') && out.includes('data-tab="BATA"'));
  assert.ok(out.includes("Toutes dépendances : ⏱ 1 h 30 · ⚡ 3.50 kWh aujourd'hui"));
  assert.ok(out.includes('<div class="title">Gîte</div>'));
  // Épinglé : pas d'onglets, total toujours visible
  const pinned = html(twoBuildings(), { batiment: "maison" });
  assert.ok(!pinned.includes("data-tab=") && pinned.includes("Toutes dépendances"));
  assert.ok(pinned.includes('<div class="title">Maison</div>'));
};

tests.render_single_building_without_tabs = () => {
  const hass = twoBuildings();
  for (const id of ["climate.gite", "climate.salon_chauffage_salon_2", "climate.ancien"]) delete hass.states[id];
  const out = html(hass);
  assert.ok(!out.includes("data-tab=") && !out.includes("Toutes dépendances"));
  assert.ok(out.includes('<div class="title">Thermostat virtuel</div>'));
};

let failed = 0;
for (const [name, fn] of Object.entries(tests)) {
  try { fn(); console.log(`ok ${name}`); } catch (err) { failed += 1; console.log(`FAIL ${name}\n${err.stack}`); }
}
process.exit(failed ? 1 : 0);
