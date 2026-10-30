const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const path = require('node:path');

// Isolate the real loader; rendering is covered by the deployed browser check.
const source = fs.readFileSync(path.join(__dirname, '../dashboard/space/assets/app.js'), 'utf8');
const loader = source.slice(source.indexOf('async function load(){'), source.lastIndexOf('nav();load();'));
const snapshot = {schema_version: 1, stocks: [], meta: {generated_at: '2026-10-29T06:08:00Z'}};
function setup(fetch, previous = snapshot) {
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {disabled: false, textContent: '', value: '', classList: {
      add() {}, remove() {}
    }});
    return elements.get(id);
  };
  let expire;
  const context = vm.createContext({$, data: previous, fetch, AbortController, Date,
    setTimeout: fn => {expire = fn; return 1;}, clearTimeout() {},
    text: (id, value) => {$(id).textContent = value;}, date: value => value,
    health() {}, models() {}, ideas() {}, commandCenter() {}, spider() {}, initStocks() {}, table() {}, lookup() {}
  });
  vm.runInContext(loader, context);
  return {context, $, expire: () => expire?.()};
}
test('refresh announces loading then reports an unchanged snapshot', async () => {
  let resolve;
  const app = setup(() => new Promise(done => {resolve = done;}));
  const pending = app.context.load();
  assert.equal(app.$('refresh').disabled, true);
  assert.match(app.$('refresh').textContent, /更新中/);
  resolve(new Response(JSON.stringify(snapshot)));
  await pending;
  assert.equal(app.$('refresh').disabled, false);
  assert.match(app.$('error').textContent, /沒有更新快照/);
  assert.match(app.$('error').textContent, /2026-10-29/);
});
test('a newer snapshot is displayed and confirmed', async () => {
  const next = {...snapshot, meta: {generated_at: '2026-10-30T00:25:00Z'}};
  const app = setup(async () => new Response(JSON.stringify(next)));
  await app.context.load();
  assert.match(app.$('error').textContent, /已載入最新已發布快照/);
  assert.match(app.$('snapshot-time').textContent, /2026-10-30/);
});
test('HTTP and invalid-data failures preserve the previous snapshot and allow retry', async () => {
  for (const response of [new Response('', {status: 503}), new Response('{}')]) {
    const app = setup(async () => response);
    await app.context.load();
    assert.equal(app.context.data, snapshot);
    assert.equal(app.$('refresh').disabled, false);
    assert.match(app.$('error').textContent, /保留上次/);
  }
});
test('a stalled request times out and re-enables refresh', async () => {
  const app = setup((_url, options) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
  }));
  const pending = app.context.load();
  app.expire();
  await pending;
  assert.equal(app.$('refresh').disabled, false);
  assert.match(app.$('error').textContent, /逾時/);
  assert.equal(app.context.data, snapshot);
});
