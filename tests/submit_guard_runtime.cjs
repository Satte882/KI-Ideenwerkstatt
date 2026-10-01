// Behavioral regression for the actual production script; no npm dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const submissions = [];
const frames = [];
const button = {
  name: 'continue_ai_handoff', value: '1', disabled: false, dataset: {},
  setAttribute() {},
};
const form = {
  dataset: {}, controls: [],
  addEventListener(type, callback) { this.listener = callback; },
  append(control) { this.controls.push(control); },
  insertAdjacentElement() {},
};
const document = {
  addEventListener(type, callback) { callback(); },
  querySelectorAll(selector) {
    return selector === 'form[data-submit-guard]' ? [form] : [];
  },
  querySelector() { return null; },
  createElement() { return { setAttribute() {} }; },
};
vm.runInNewContext(fs.readFileSync('static/js/copilot-submit-guard.js', 'utf8'), {
  document,
  window: { addEventListener() {}, requestAnimationFrame(callback) { frames.push(callback); } },
  HTMLFormElement: { prototype: { submit() {
    submissions.push(this.controls.map(({name, value}) => [name, value]));
  } } },
});
let prevented = 0;
const submit = () => form.listener({ submitter: button, preventDefault() { prevented++; } });
submit();
assert.equal(button.disabled, true);
submit(); // A second click before the delayed native submit cannot duplicate the action.
while (frames.length) frames.shift()();
assert.equal(prevented, 2);
assert.equal(submissions.length, 1);
assert.deepEqual(submissions[0], [['continue_ai_handoff', '1']]);
console.log('PASS: clicked continuation action survives busy state; one submission');
