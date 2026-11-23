const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/mapFollow.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, {exports: moduleExports});
const {followTourNode} = moduleExports;

test('follows an off-screen measured node and keeps the current zoom', () => {
 const calls = [];
 const flow = {
  getInternalNode: () => ({measured: {width: 100, height: 60}, internals: {positionAbsolute: {x: 700, y: 300}}}),
  getViewport: () => ({x: 0, y: 0, zoom: 1.25}),
  setCenter: (x, y, options) => calls.push({x, y, zoom: options.zoom})
 };
 followTourNode(flow, 'service', {width: 500, height: 400});
 assert.deepEqual(calls, [{x: 750, y: 330, zoom: 1.25}]);
});

test('leaves visible nodes and unmeasured nodes alone', () => {
 let calls = 0;
 const flow = {
  getInternalNode: () => ({measured: {width: 100, height: 60}, internals: {positionAbsolute: {x: 120, y: 120}}}),
  getViewport: () => ({x: 0, y: 0, zoom: 1}),
  setCenter: () => { calls++; }
 };
 followTourNode(flow, 'visible', {width: 500, height: 400});
 flow.getInternalNode = () => ({measured: {}, internals: {positionAbsolute: {x: 700, y: 300}}});
 followTourNode(flow, 'unmeasured', {width: 500, height: 400});
 assert.equal(calls, 0);
});
