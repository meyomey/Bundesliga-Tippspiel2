'use strict';
/* (92) Node-Test: Theme-Umschalter-Logik (DOM + localStorage Stub) */
const attrs = new Map();
global.document = {
  documentElement: {
    getAttribute: (k) => (attrs.has(k) ? attrs.get(k) : null),
    setAttribute: (k, v) => attrs.set(k, v),
  },
  readyState: 'complete',
  getElementById: () => null,
  addEventListener: () => {},
};
const store = new Map();
global.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
};

const api = require('../../static/js/theme.js');

// 1) Default dunkel (leerer Speicher)
if (api.initialTheme() !== 'dark') throw new Error('Default muss dark sein');

// 2) anwenden('light') setzt Attribut, Rueckgabe normiert
if (api.anwenden('light') !== 'light') throw new Error('anwenden(light) falsch');
if (attrs.get('data-theme') !== 'light') throw new Error('Attribut nicht gesetzt');

// 3) anwenden mit Quatsch faellt auf dark zurueck
if (api.anwenden('neon-pink') !== 'dark') throw new Error('ungueltiges Theme muss auf dark fallen');

// 4) umschalten: Stand nach Schritt 3 = dark -> also light, persistiert
if (api.umschalten() !== 'light') throw new Error('umschalten dark->light falsch');
if (store.get('theme') !== 'light') throw new Error('Persistenz fehlt');

// 5) umschalten: light -> dark, persistiert
if (api.umschalten() !== 'dark') throw new Error('umschalten light->dark falsch');
if (store.get('theme') !== 'dark') throw new Error('Persistenz fehlt (2)');

// 6) initialTheme liest gespeicherten Wert
if (api.initialTheme() !== 'dark') throw new Error('initialTheme liest Speicher nicht');

console.log('theme_test: alle Assertions gruen');
