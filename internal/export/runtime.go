package export

// runtimeJS is deliberately constant. No document, translation, view value, or
// generated JSON is ever interpolated into a script element.
const runtimeJS = `(function(){
'use strict';
var d=document,root=d.documentElement;root.classList.add('dr-js');
var origin='',originInlineView='',lastChapter='c01',isInline=root.getAttribute('data-face')==='inline'||root.getAttribute('data-face')==='hybrid';
function all(s,c){return Array.prototype.slice.call((c||d).querySelectorAll(s));}
function one(s,c){return (c||d).querySelector(s);}
function face(name){root.setAttribute('data-face',name);all('[data-face-target]').forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-face-target')===name?'true':'false');});}
function inlineView(mode){root.setAttribute('data-inline-view',mode);all('[data-inline-view-target]').forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-inline-view-target')===mode?'true':'false');});}
function lang(mode){root.setAttribute('data-lang-mode',mode);all('[data-language]').forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-language')===mode?'true':'false');});}
function chapter(id){var chapters=all('[data-chapter]');if(!chapters.length)return;if(!chapters.some(function(c){return c.getAttribute('data-chapter')===id;}))id=chapters[0].getAttribute('data-chapter');lastChapter=id;root.setAttribute('data-chapter',id);chapters.forEach(function(c){c.hidden=c.getAttribute('data-chapter')!==id;});all('[data-chapter-link]').forEach(function(b){b.setAttribute('aria-current',b.getAttribute('data-chapter-link')===id?'location':'false');});}
function jump(target,toFace){var el=d.getElementById(target.replace(/^#/,''));if(!el)return;var ch=el.closest('[data-chapter]');if(ch)chapter(ch.getAttribute('data-chapter'));if(isInline){if(toFace==='read')inlineView('mixed');else if(toFace==='genui'&&root.getAttribute('data-inline-view')==='prose')inlineView('mixed');}else if(toFace){face(toFace);}location.hash=target;setTimeout(function(){el.scrollIntoView({behavior:'smooth',block:'start'});el.classList.remove('dr-highlight');void el.offsetWidth;el.classList.add('dr-highlight');},0);}
if(isInline){inlineView('mixed');}else{face(root.getAttribute('data-face')==='read'?'read':'genui');}
lang(root.getAttribute('data-lang-mode')||'original');
var first=one('[data-chapter]');if(first)chapter(first.getAttribute('data-chapter'));
all('[data-face-target]').forEach(function(b){b.addEventListener('click',function(){face(b.getAttribute('data-face-target'));});});
all('[data-inline-view-target]').forEach(function(b){b.addEventListener('click',function(){inlineView(b.getAttribute('data-inline-view-target'));});});
all('[data-language]').forEach(function(b){b.addEventListener('click',function(){lang(b.getAttribute('data-language'));});});
all('[data-chapter-link]').forEach(function(b){b.addEventListener('click',function(){chapter(b.getAttribute('data-chapter-link'));var drawer=one('#dr-toc');if(drawer)drawer.open=false;});});
all('[data-chapter-step]').forEach(function(b){b.addEventListener('click',function(){var cs=all('[data-chapter]'),i=cs.findIndex(function(c){return c.getAttribute('data-chapter')===lastChapter;});i=Math.max(0,Math.min(cs.length-1,i+Number(b.getAttribute('data-chapter-step'))));chapter(cs[i].getAttribute('data-chapter'));var top=one('#c'+String(i+1).padStart(2,'0'));if(top)top.scrollIntoView({behavior:'smooth'});});});
all('[data-jump-target]').forEach(function(b){b.addEventListener('click',function(ev){var target=b.getAttribute('data-jump-target');origin=b.getAttribute('data-origin')||'';originInlineView=isInline?(root.getAttribute('data-inline-view')||'mixed'):'';if(origin){ev.preventDefault();location.hash=target;jump(target,'read');var back=one('[data-back-genui]');if(back)back.hidden=false;}else{jump(target,'read');}});});
all('[data-jump-genui]').forEach(function(b){b.addEventListener('click',function(ev){ev.preventDefault();var target=b.getAttribute('data-jump-genui');jump(target,'genui');});});
var back=one('[data-back-genui]');if(back)back.addEventListener('click',function(){if(isInline&&originInlineView)inlineView(originInlineView);if(origin)jump(origin,'genui');else if(!isInline)face('genui');back.hidden=true;});
function output(island,key){var t=one('template[data-island="'+island+'"][data-state="'+key+'"]');var out=one('.dr-island-output[data-island="'+island+'"]');if(t&&out){out.replaceChildren(t.content.cloneNode(true));out.setAttribute('data-state',key);var box=out.closest('.dr-island');if(box)box.setAttribute('data-state',key);}}
function syncControls(island,state){var parts=state.split('.');all('[data-island="'+island+'"][data-control]').forEach(function(c){var i=Number(c.getAttribute('data-control')),v=parts[i];if(c.type==='checkbox')c.checked=v==='1';else if(c.type==='radio')c.checked=c.value===v;else if(c.type==='button')c.setAttribute('aria-pressed',c.getAttribute('data-value-index')===v?'true':'false');else c.value=v;});}
function setControl(c){var island=c.getAttribute('data-island'),box=c.closest('.dr-island');if(!box)return;var state=(box.getAttribute('data-state')||'0').split('.');state[Number(c.getAttribute('data-control'))]=c.type==='checkbox'?(c.checked?'1':'0'):c.value;state=state.join('.');output(island,state);syncControls(island,state);}
all('[data-island][data-control]').forEach(function(c){var event=c.tagName==='SELECT'||c.type==='checkbox'||c.type==='radio'||c.type==='button'?'click':'input';if(c.tagName==='SELECT'||c.type==='checkbox'||c.type==='radio')event='change';c.addEventListener(event,function(){setControl(c);});});
all('[data-island][data-action]').forEach(function(b){b.addEventListener('click',function(){var island=b.getAttribute('data-island'),box=b.closest('.dr-island');if(!box)return;var from=box.getAttribute('data-state')||'0',action=b.getAttribute('data-action');var tr=one('[data-island-transition="'+island+'"][data-action="'+action+'"][data-from="'+from+'"]');if(tr){var to=tr.getAttribute('data-to');output(island,to);syncControls(island,to);}});});
all('[data-copy-code]').forEach(function(b){b.addEventListener('click',function(){var text=b.getAttribute('data-copy-code'),done=function(){var old=b.textContent;b.textContent='已复制';setTimeout(function(){b.textContent=old;},900);};if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(text).then(done,function(){});else{var ta=d.createElement('textarea');ta.value=text;d.body.appendChild(ta);ta.select();try{if(d.execCommand('copy'))done();}catch(e){}ta.remove();}});});
})();`
