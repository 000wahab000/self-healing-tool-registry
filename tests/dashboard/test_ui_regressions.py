"""Focused browser-logic regressions for the dashboard stepper."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).parents[2] / "dashboard" / "index.html"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
def test_ac_56_stepper_keeps_task_context_and_failure_states():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const page = fs.readFileSync(process.argv[1], 'utf8');
const section = (start, end) => {
  const a = page.indexOf(start), b = page.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error(`dashboard section missing: ${start}`);
  return page.slice(a, b);
};
const context = {
  MAX_CALLS: 10,
  TOOLS: ['get_user','update_email','set_manager','create_ticket'],
  SINGLE_TOOL_RUNS: {M8:['create_ticket'], 'M6-N':['set_manager']},
  CONTROL_TOOLS: {C2:['get_user'], C3:['get_user','update_email']},
  STEP_LABEL: {get_user:'Look up user', update_email:'Set email', set_manager:'Set manager', create_ticket:'Open ticket'},
  document: {createElement: (tag) => ({tag, attrs:{}, children:[], setAttribute(k,v){this.attrs[k]=v;}, append(...nodes){this.children.push(...nodes);}})},
};
const source = section('function el(tag, text, attrs) {', 'function note(text)') +
  section('function outcomeInfo(h) {', 'function outcomePill(h)') +
  section('function stepState(ts, tool, o) {', '/* Drift banner:') +
  section('function stat(label, value) {', 'function renderRun(agent, s) {') +
  section('function renderRun(agent, s) {', 'function renderHeals(heals) {');
const selection = section('const tools = (res.agent ===', ';').replace(/^const tools = /, '');
vm.createContext(context);
vm.runInContext(source + '\nthis.renderSteps = renderSteps; this.renderRun = renderRun; this.stat = stat;', context);
const choose = (agent, mutation) => vm.runInContext(`(function(){ const res={agent:${JSON.stringify(agent)},mutation:${JSON.stringify(mutation)}}; return (${selection}); })()`, context);
const tools = choose('scripted','M8');
if (tools.length !== 4) throw new Error('scripted M8 must use all task tools');
const box = {children:[], replaceChildren(...children){this.children=children;}};
const traces = tools.map((tool) => ({tool,error_class: tool === 'create_ticket' ? 'E2' : 'OK'}));
const refusal = {tool:'create_ticket',outcome:'ABORTED',reason:'NO_SAFE_VALUE',tier:1};
context.renderSteps(box, tools, traces, {heals:{create_ticket:refusal},done:true});
if (box.children.length !== 4 || box.children[3].attrs['data-k'] !== 'refused') throw new Error('scripted M8 must retain all four steps and refusal');
const llmTools = choose('llm','M8');
context.renderSteps(box, llmTools, [traces[3]], {heals:{create_ticket:refusal},done:true});
if (box.children.length !== 1 || box.children[0].children[1].textContent !== 'create_ticket') throw new Error('single-tool M8 must show only the ticket step');
const liveTools = choose('scripted','M8');
if (liveTools.length !== 4) throw new Error('live scripted stream must retain all four steps');
context.renderSteps(box, tools, tools.map(tool => ({tool,error_class:tool === 'get_user' ? 'E2' : 'OK'})), {capped:true,total:10,done:true});
if (box.children[0].attrs['data-k'] !== 'fail' || !box.children[0].attrs.class.includes('capped')) throw new Error('capped baseline failure must be red and non-pulsing');
context.renderSteps(box, tools, tools.map(tool => ({tool,error_class:'OK'})), {done:true,details:{tickets:{checked:true,ok:false}}});
if (box.children[3].attrs['data-k'] !== 'silent' || /nothing saved/i.test(box.children[3].children[2].textContent)) throw new Error('ticket mismatch must be reported');
const elements = {};
context.$ = (id) => elements[id] || (elements[id] = {className:'',textContent:'',hidden:false,children:[],replaceChildren(...children){this.children=children;}});
context.exploreRes = null;
context.TOOLS = tools;
context.liveCalls = {baseline:[]};
context.counts = {baseline:0};
context.lastLiveMut = null;
context.renderSteps = () => {};
const state = (hit_limit, data_correct=true, error=null) => ({runs:{baseline:{hit_limit,status:'done',data_correct,error,llm_tokens:0}},mocks:{baseline:{data:{users:{'123':{email:'a@example.com',manager_id:null}},tickets:[]}}}});
context.renderRun('baseline', state(true));
if (elements['status-baseline'].className !== 'pill bad') throw new Error('live iteration cap must be red');
context.renderRun('baseline', state(false));
if (elements['status-baseline'].className !== 'pill good') throw new Error('live completed run must be green');
context.renderRun('baseline', state(false, false));
if (elements['status-baseline'].className !== 'pill bad') throw new Error('live incorrect final state must be red');
context.renderRun('baseline', state(false, true, 'provider failed'));
if (elements['status-baseline'].className !== 'pill bad') throw new Error('provider failure must not be green');
context.counts.baseline = 2;
context.exploreRes = {baseline:{tool_calls:7,data_state:null}};
context.renderRun('baseline', state(false));
const stats = elements['stats-baseline'].children;
if (stats[0].children[1].textContent !== '7') throw new Error('preset stats must use the shown run call count');
if (stats[1].children[1].textContent !== 'a@example.com') throw new Error('null preset data_state must fall back to bootstrap data');
"""
    subprocess.run(["node", "-e", script, str(PAGE)], check=True, capture_output=True, text=True)


def test_ac_56_email_stat_can_wrap_full_address():
    page = PAGE.read_text(encoding="utf-8")
    stat_rule = page.split(".stat b {", 1)[1].split("}", 1)[0]
    assert "overflow-wrap: anywhere" in stat_rule or "overflow-wrap: break-word" in stat_rule
    email_span = page.split(".stat:nth-child(2)", 1)[1].split("}", 1)[0]
    assert "grid-column: span 2" in email_span
