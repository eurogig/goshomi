import React, {useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ReactFlow, Background, Controls, MarkerType, type Node, type Edge, type ReactFlowInstance} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import Prism from 'prismjs';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-tsx';
import {ArrowLeft, ArrowRight, Check, ChevronDown, Code2, Compass, GitBranch, Layers3, MousePointer2, Shield, Sparkles, Maximize2, X, Copy, ExternalLink, Bug} from 'lucide-react';
import './style.css';
import {followTourNode} from './mapFollow';

type Ref = {path:string;start:number;end:number;symbol?:string};
type Reference = {title:string;url:string};
type Risk = {asset:string;boundary:string;scenario:string;consequence:string;control:string;mitigation:string;confidence:string;attackPath?:string[];assessment?:{level:'High'|'Medium'|'Low'|'Needs verification';rationale:string;references:Reference[]};mitigationPrompt?:string};
type Finding = {status:'confirmed'|'needs verification';severity:'Critical'|'High'|'Medium'|'Low'|'Informational'|'Needs verification';issue:string;reachability:string;impact:string;fixExplanation:string;fixCode:string;fixPrompt:string;fixPatch?:string};
type Step = {id:string;title:string;body:string;node:string;refs:Ref[];status?:string;input?:string;output?:string;risk?:Risk;finding?:Finding};
type Chapter = {id:string;title:string;eyebrow:string;intro:string;steps:Step[]};
type TourNode = {id:string;label:string;kind:string;description:string;refs:Ref[];position:{x:number;y:number}};
type Tour = {repository:{name:string;description:string;technologies:string[];revision:string|null;generatedAt:string;snapshot:string};nodes:TourNode[];edges:{source:string;target:string;label:string}[];chapters:Chapter[];sources:Record<string,{content:string;sha256:string}>};
const tour = (window as unknown as { GOSHOMI_TOUR: Tour }).GOSHOMI_TOUR;
if (!tour) throw new Error('Tour data is missing from this generated page.');
const icons = [Compass,Layers3,Code2,GitBranch,Sparkles,GitBranch,Bug,Shield];
const chapterColors=['#a993ff','#83b7ed','#7ccbb7','#e7b778','#d9a1d9','#9faee8','#f0a56d','#ed858d'];

function FindingDetails({finding}:{finding:Finding}){
 const [copied,setCopied]=useState<'idle'|'code'|'prompt'|'patch'|'failed'>('idle');
 const dialog=useRef<HTMLDialogElement>(null);
 const downloadPatch=async()=>{if(!finding.fixPatch)return;let suffix='';try{const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(finding.issue+'\n'+finding.fixPatch));suffix=Array.from(new Uint8Array(bytes)).slice(0,6).map(b=>b.toString(16).padStart(2,'0')).join('')}catch{suffix=String(Date.now())}const slug=finding.issue.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,44)||'finding';const url=URL.createObjectURL(new Blob([finding.fixPatch],{type:'text/x-diff;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`goshomi-${slug}-${suffix}.patch`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 const copy=async(value:string,kind:'code'|'prompt'|'patch')=>{try{await navigator.clipboard.writeText(value);setCopied(kind)}catch{setCopied('failed')}};
 return <div className="code-finding">
  <div className="finding-head"><span>CODE REVIEW FINDING</span><b className={'finding-status '+(finding.status==='confirmed'?'confirmed':'unverified')}>{finding.status==='confirmed'?'Confirmed in source':'Needs verification'}</b><b className="finding-severity">{finding.severity}</b></div>
  <section><small>VULNERABILITY</small><p>{finding.issue}</p></section>
  <section><small>REACHABILITY</small><p>{finding.reachability}</p></section>
  <section><small>POTENTIAL IMPACT</small><p>{finding.impact}</p></section>
  <section><small>FIX</small><p>{finding.fixExplanation}</p><div className="fix-code-label">KEY CHANGE EXAMPLE</div><pre><code>{finding.fixCode}</code></pre><div className="fix-actions"><button className="finding-copy" onClick={()=>copy(finding.fixCode,'code')}><Copy size={13}/>{copied==='code'?'Copied example':'Copy example'}</button>{finding.fixPatch&&<button className="finding-copy" onClick={()=>dialog.current?.showModal()}>View full Git patch</button>}</div>{finding.fixPatch&&<dialog ref={dialog} className="patch-dialog" aria-labelledby="patch-title"><h2 id="patch-title">Proposed Git patch</h2><p>Review the repo path and surrounding changes before applying. This patch is a proposal; inspect it and run relevant checks.</p><pre><code>{finding.fixPatch}</code></pre><div className="patch-actions"><button className="finding-copy" onClick={()=>copy(finding.fixPatch!,'patch')}><Copy size={13}/>{copied==='patch'?'Copied patch':'Copy patch'}</button><button className="finding-copy" onClick={downloadPatch}>Download .patch</button><button className="finding-copy" onClick={()=>dialog.current?.close()}>Close</button></div></dialog>}{!finding.fixPatch&&<p className="patch-unavailable">No downloadable patch was proposed. See the fix explanation and prompt for the unresolved context.</p>}</section>
  <section className="finding-prompt"><div><small>FIX PROMPT</small><button className="finding-copy" onClick={()=>copy(finding.fixPrompt,'prompt')}><Copy size={13}/>{copied==='prompt'?'Copied prompt':'Copy prompt'}</button></div><textarea readOnly value={finding.fixPrompt} rows={5}/>{copied==='failed'&&<small>Clipboard unavailable. Select and copy the text manually.</small>}</section>
 </div>
}

function validReference(url:string){
 try{const parsed=new URL(url);const host=parsed.hostname.toLowerCase();return parsed.protocol==='https:'&&!parsed.username&&!parsed.password&&(!parsed.port||parsed.port==='443')&&(host==='owasp.org'||host.endsWith('.owasp.org')||host==='mitre.org'||host.endsWith('.mitre.org'))}catch{return false}
}
function RiskDetails({risk}:{risk:Risk}){
 const [copyState,setCopyState]=useState<'idle'|'copied'|'failed'>('idle');
 const fields:[string,string][]=[['ASSET',risk.asset],['BOUNDARY',risk.boundary],['SCENARIO',risk.scenario],['CONSEQUENCE',risk.consequence],['OBSERVED CONTROL',risk.control],['MITIGATION',risk.mitigation],['CONFIDENCE',risk.confidence]];
 const assessment=risk.assessment;
 const copyPrompt=async()=>{
  try{if(!navigator.clipboard?.writeText)throw new Error('Clipboard unavailable');await navigator.clipboard.writeText(risk.mitigationPrompt!);setCopyState('copied')}
  catch{setCopyState('failed')}
 };
 return <>
  <div className="risk-assessment"><div className="risk-assessment-head"><small>RISK</small><span className={'risk-level '+(assessment?.level==='High'?'risk-high':assessment?.level==='Medium'?'risk-medium':assessment?.level==='Low'?'risk-low':'risk-unknown')}>{assessment?.level||'Not assessed'}</span></div>
   <p>{assessment?.rationale||'This tour predates qualitative risk assessments. Regenerate it to assess this finding.'}</p>
   {assessment?.references?.filter(reference=>validReference(reference.url)).length ? <div className="risk-references"><small>POSSIBLE FRAMEWORK MAPPINGS</small>{assessment.references.filter(reference=>validReference(reference.url)).map(reference=><a href={reference.url} target="_blank" rel="noopener noreferrer" key={reference.url}>{reference.title} <ExternalLink size={12}/></a>)}</div> : null}
  </div>
  <div className="risk-grid">{fields.map(([label,value])=><div key={label}><small>{label}</small><p>{value}</p></div>)}</div>
  {risk.mitigationPrompt ? <div className="mitigation-prompt"><div className="mitigation-prompt-head"><div><small>SUGGESTED MITIGATION PROMPT</small><span>Review before pasting into your coding agent</span></div><button onClick={copyPrompt}><Copy size={14}/>{copyState==='copied'?'Copied':'Copy prompt'}</button></div><textarea aria-label="Suggested mitigation prompt" readOnly value={risk.mitigationPrompt} rows={5}/><span className="copy-status" role="status">{copyState==='failed'?'Clipboard unavailable. Select the prompt and copy it manually.':copyState==='copied'?'Copied to clipboard.':''}</span></div> : <p className="prompt-unavailable">A mitigation prompt is not available in this tour. Regenerate it to create one.</p>}
 </>
}
function App(){
 const [ci,setCi]=useState(0),[si,setSi]=useState(0),[selected,setSelected]=useState<string|null>(null),[refIndex,setRefIndex]=useState(0),[mobile,setMobile]=useState<'tour'|'source'>('tour'),[expanded,setExpanded]=useState(false),[expandedPanel,setExpandedPanel]=useState<'tour'|'source'>('tour');
 const chapter=tour.chapters[ci], step=chapter.steps[si], active=selected || step.node, node=tour.nodes.find(n=>n.id===active);
 const refs=selected && node ? node.refs : step.refs; const reference=refs[Math.min(refIndex,refs.length-1)];
 const source=tour.sources[reference?.path]?.content || '';
 const codeRef=useRef<HTMLDivElement>(null);
 const flowRef=useRef<ReactFlowInstance | null>(null);
 const diagramRef=useRef<HTMLDivElement>(null);
 const wasExpanded=useRef(false);
 useEffect(()=>{setRefIndex(0)},[ci,si,selected]);
 useEffect(()=>{if(codeRef.current){codeRef.current.scrollTop=0;codeRef.current.scrollLeft=0;}},[reference?.path,reference?.start,reference?.end,mobile]);
 useEffect(()=>{const timer=window.setTimeout(()=>flowRef.current?.fitView({padding:0.15,duration:200}),80);return ()=>window.clearTimeout(timer)},[expanded]);
 useEffect(()=>{
  const alreadyExpanded=wasExpanded.current; wasExpanded.current=expanded;
  if(!expanded||!alreadyExpanded)return;
  const frame=window.requestAnimationFrame(()=>{
   const flow=flowRef.current, diagram=diagramRef.current;
   if(flow&&diagram)followTourNode(flow,active,diagram.getBoundingClientRect());
  });
  return ()=>window.cancelAnimationFrame(frame);
 },[expanded,ci,si,active]);
 useEffect(()=>{if(!expanded)return;const close=(e:KeyboardEvent)=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]'))setExpanded(false)};window.addEventListener('keydown',close);return ()=>window.removeEventListener('keydown',close)},[expanded]);
 const nodes:Node[]=useMemo(()=>tour.nodes.map(n=>({id:n.id,position:n.position,data:{label:<><small>{n.kind}</small><strong>{n.label}</strong><span>{n.id===active?'Viewing source':'View component'} <ArrowRight size={13}/></span></>},className:`architecture-node ${n.id===active?'active':''} ${ci===7&&n.id===active?'boundary':''}`})),[active,ci]);
 const attackPath=ci===7 ? step.risk?.attackPath : undefined;
 const edges:Edge[]=useMemo(()=>{
   const base=tour.edges.map((e,i)=>({id:String(i),source:e.source,target:e.target,label:e.label,animated:!attackPath&&ci!==7&&(e.source===active||e.target===active),markerEnd:{type:MarkerType.ArrowClosed,color:!attackPath&&ci!==7&&(e.source===active||e.target===active)?chapterColors[ci]:'#626a80'},style:{stroke:!attackPath&&ci!==7&&(e.source===active||e.target===active)?chapterColors[ci]:'#414756',strokeWidth:1.4,opacity:attackPath?0.4:1},labelStyle:{fill:'#9aa1b3',fontSize:11},labelBgStyle:{fill:'#151922'}}));
   const riskEdges:Edge[]=attackPath?.slice(1).map((target,i)=>({id:`risk-${i}`,source:attackPath[i],target,animated:true,markerEnd:{type:MarkerType.ArrowClosed,color:'#f07882'},style:{stroke:'#f07882',strokeWidth:3,strokeDasharray:'7 5'},label:`${i+1}`,labelStyle:{fill:'#ffd5d8',fontWeight:700,fontSize:11},labelBgStyle:{fill:'#512e35'}}))||[];
   return [...base,...riskEdges];
 },[active,ci,attackPath]);
 const go=(c:number,s:number)=>{setCi(c);setSi(s);setSelected(null)};
 const next=()=>{if(si<chapter.steps.length-1)go(ci,si+1);else if(ci<tour.chapters.length-1)go(ci+1,0)};
 const prev=()=>{if(si>0)go(ci,si-1);else if(ci>0)go(ci-1,tour.chapters[ci-1].steps.length-1)};
 const total=tour.chapters.reduce((n,c)=>n+c.steps.length,0), done=tour.chapters.slice(0,ci).reduce((n,c)=>n+c.steps.length,0)+si+1;
 const language=reference?.path.endsWith('.json')?'javascript':reference?.path.endsWith('.tsx')?'tsx':reference?.path.endsWith('.ts')?'typescript':'javascript';
 const highlighted=Prism.highlight(source,Prism.languages[language]||Prism.languages.javascript,language).split('\n');
 return <div className={`app chapter-theme-${ci} ${expanded?"map-expanded":""}`}><aside className="sidebar"><div className="brand"><div className="brandmark"><Compass size={20}/></div><div><b>goshomi<span>.</span></b><small>Your Code. Explained.</small></div></div><div className="project"><div className="project-icon"><Code2 size={17}/></div><div><small>YOUR REPOSITORY</small><strong>{tour.repository.name}</strong></div><ChevronDown size={15}/></div><div className="sidebar-label">YOUR GUIDED TOUR <span>{String(ci+1).padStart(2,'0')} / 08</span></div><nav>{tour.chapters.map((c,i)=>{const Icon=icons[i]||Compass;return <button key={c.id} className={'chapter '+(i===ci?'current':'')} onClick={()=>go(i,0)}><Icon size={17}/><span>{c.title}</span>{i<ci&&<Check size={14}/>}</button>})}</nav><div className="sidebar-bottom"><div className="progress-label"><span>YOUR PROGRESS</span><b>{Math.round(done/total*100)}%</b></div><div className="progress"><i style={{width:`${done/total*100}%`}}/></div><p>{done} of {total} stops explored</p><div className="snapshot"><GitBranch size={14}/><span>{tour.repository.revision?.slice(0,7)||'Uncommitted snapshot'}</span><span>·</span><span title={`Generated ${tour.repository.generatedAt}; run the verify command to check for changes`}>{new Date(tour.repository.generatedAt).toLocaleDateString()}</span></div></div></aside>
 <main className="main"><header className="topbar"><div><span className="top-muted">THE TOUR</span><span className="slash">/</span><b>{chapter.title}</b></div><div className="top-right"><span className="live-dot"/> SOURCE-GROUNDED <span className="top-divider"/> <span>{tour.repository.technologies.slice(0,3).join('  ·  ')}</span></div></header><div className="mobile-switch"><button className={mobile==='tour'?'on':''} onClick={()=>setMobile('tour')}>Tour</button><button className={mobile==='source'?'on':''} onClick={()=>setMobile('source')}>Source</button></div><div className={'workspace '+(mobile==='source'?'show-source ':'')+(expanded&&expandedPanel==='source'?'expanded-source':'')}><section className="story">{expanded&&<div className="expanded-panel-switch" aria-label="Expanded view panel"><button className={expandedPanel==='tour'?'on':''} onClick={()=>setExpandedPanel('tour')}>Tour</button><button className={expandedPanel==='source'?'on':''} onClick={()=>setExpandedPanel('source')}>Source evidence</button></div>}<div className="story-scroll"><div className="breadcrumb"><span>CHAPTER {String(ci+1).padStart(2,'0')}</span><i/> {chapter.eyebrow}</div><h1>{chapter.title}<span>.</span></h1><p className="intro">{chapter.intro}</p><div className="diagram-header"><div><span className="section-icon"><Layers3 size={15}/></span><b>{ci===7?'Security boundary':'Architecture map'}</b><span className="diagram-sub">{ci===7?'SELECT A SCENARIO':'HOW THE PIECES CONNECT'}</span></div><div className="diagram-actions"><span className="explore"><MousePointer2 size={13}/> SELECT A COMPONENT</span><button className="expand-map" onClick={()=>setExpanded(true)} aria-label="Expand architecture map"><Maximize2 size={14}/> Expand map</button></div></div><div ref={diagramRef} className={"diagram "+(expanded?"is-expanded":"")} role="region" aria-label={expanded?"Expanded architecture map":"Architecture map"}>{expanded&&<div className="expanded-map-header"><div><b>{ci===7?'Security boundary':'Architecture map'}</b><span>Select a component to explore</span></div><button onClick={()=>setExpanded(false)} aria-label="Close expanded map"><X size={16}/> Close <kbd>esc</kbd></button></div>}<ReactFlow nodes={nodes} edges={edges} onInit={instance=>{flowRef.current=instance}} onNodeClick={(_,n)=>{setSelected(n.id);setMobile('tour');setExpandedPanel('tour')}} fitView minZoom={0.35} maxZoom={1.5} nodesDraggable={false} proOptions={{hideAttribution:true}}><Background color="#303442" gap={20} size={1}/><Controls showInteractive={false}/></ReactFlow></div>{ci===7&&<div className="boundary-note"><Shield size={14}/>{attackPath ? 'Red dashed arrows show a potential attack path, not a confirmed exploit.' : 'Dashed outline marks the component associated with this scenario. No attack path was specified.'}</div>}<div className="narrative"><div className="section-kicker">{selected?'COMPONENT DETAILS':`STOP ${String(si+1).padStart(2,'0')} / ${String(chapter.steps.length).padStart(2,'0')}`} <span>{selected?'VERIFIED SOURCE':step.status?.toUpperCase()}</span></div><h2>{selected?node?.label:step.title}</h2><p>{selected?node?.description:step.body}</p>{selected&&<><div className="relation"><b>CONNECTED TO</b> {tour.edges.filter(e=>e.source===selected||e.target===selected).map(e=>tour.nodes.find(n=>n.id===(e.source===selected?e.target:e.source))?.label).join(' · ')||'No recorded relationships'}</div><button className="text-button" onClick={()=>setSelected(null)}>← Back to guided stop</button></>}{!selected&&step.input&&<div className="flow-detail"><div><small>INPUT</small>{step.input}</div><ArrowRight size={17}/><div><small>OUTPUT</small>{step.output}</div></div>}{!selected&&step.finding&&<FindingDetails key={step.id} finding={step.finding}/>} {!selected&&step.risk&&<RiskDetails key={step.id} risk={step.risk}/>}</div><div className="step-dots">{chapter.steps.map((s,i)=><button key={s.id} aria-label={`Go to ${s.title}`} className={i===si?'active':''} onClick={()=>go(ci,i)}/>)}</div></div><footer className="story-footer"><button onClick={prev} disabled={ci===0&&si===0}><ArrowLeft size={16}/> Previous</button><span>{si+1} <em>/</em> {chapter.steps.length}</span><button className="next" onClick={next} disabled={ci===tour.chapters.length-1&&si===chapter.steps.length-1}>Next stop <ArrowRight size={16}/></button></footer></section>
 <aside className="source-panel"><div className="source-heading"><div><span className="source-icon"><Code2 size={16}/></span><div><b>Source evidence</b><small>THE CODE BEHIND THE STORY</small></div></div><span className="verified"><Check size={12}/> LINKED</span></div><div className="file-bar"><div><span className="file-icon">{reference?.path.split('.').pop()?.toUpperCase()}</span><div><b>{reference?.path.split('/').pop()}</b><small>{reference?.path}</small></div></div></div>{refs.length>1&&<div className="references">{refs.map((r,i)=><button className={i===refIndex?'active':''} key={i} onClick={()=>setRefIndex(i)}>{r.symbol||r.path.split('/').pop()}</button>)}</div>}<div className="code-scroll" ref={codeRef}><div className="code">{highlighted.slice((reference?.start||1)-1,reference?.end).map((line,i)=><div key={i} className="code-line highlighted"><span className="line-number">{(reference?.start||1)+i}</span><code dangerouslySetInnerHTML={{__html:line||' '}}/></div>)}</div></div><div className="source-bottom"><span><i/> LINES {reference?.start}–{reference?.end}</span><span>{reference?.symbol||'SOURCE REFERENCE'}</span></div></aside></div></main></div>
}

createRoot(document.getElementById('root')!).render(<App/>);
