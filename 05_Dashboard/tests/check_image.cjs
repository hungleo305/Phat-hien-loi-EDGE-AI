const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const source = fs.readFileSync(__dirname + '/../station/dashboard.js', 'utf8');
const functions = source.slice(source.indexOf('function clearCaptureImage()'), source.indexOf('function renderCounts'));
const nodes = {
  captureImage: {hidden: false, src: 'old', removeAttribute(name) { delete this[name]; }},
  captureEmpty: {hidden: true}
};
const pending = [];
let urls = 0;
const context = vm.createContext({
  $: id => nodes[id],
  api: () => new Promise(resolve => pending.push(resolve)),
  URL: {createObjectURL: () => `blob:${++urls}`, revokeObjectURL() {}}
});
vm.runInContext("let currentImage = null; let currentImageUrl = ''; let captureRequestVersion = 0;\n" + functions, context);
(async () => {
  const old = vm.runInContext("showImage('/old.jpg')", context);
  vm.runInContext('clearCaptureImage()', context);
  pending.shift()({blob: async () => ({})});
  await old;
  assert.equal(nodes.captureImage.hidden, true);
  assert.equal(nodes.captureImage.src, undefined);
  assert.equal(nodes.captureEmpty.hidden, false);
  const first = vm.runInContext("showImage('/first.jpg')", context);
  const second = vm.runInContext("showImage('/second.jpg')", context);
  const [resolveFirst, resolveSecond] = pending.splice(0);
  resolveSecond({blob: async () => ({})});
  await second;
  const newest = nodes.captureImage.src;
  resolveFirst({blob: async () => ({})});
  await first;
  assert.equal(nodes.captureImage.src, newest);
  assert.equal(nodes.captureEmpty.hidden, true);
  vm.runInContext('clearCaptureImage()', context);
  assert.equal(nodes.captureImage.hidden, true);
  assert.equal(nodes.captureEmpty.hidden, false);
  console.log('PASS: reset removes old image, ignores late responses, preserves newest image');
})().catch(error => { console.error(error); process.exitCode = 1; });
