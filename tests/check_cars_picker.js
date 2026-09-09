const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.listeners={};this.hidden=false;this.disabled=false;this.textContent='';}
 append(...nodes){this.children.push(...nodes);}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k];}
 addEventListener(k,fn){this.listeners[k]=fn;}scrollIntoView(){}replaceChildren(...nodes){this.children=nodes;}
}
const elements={};const get=id=>elements[id]??=(new Element('div'));
get('search-form').elements={namedItem:get};
const context={document:{getElementById:get,createElement:t=>new Element(t)},Intl,URL,console,setTimeout:()=>{}};
vm.createContext(context);
let source=fs.readFileSync(process.argv[2],'utf8');source=source.slice(0,source.lastIndexOf("document.querySelectorAll('[data-nav]')"));
vm.runInContext(source,context);
vm.runInContext(`selectModule=()=>{module='cars';};updateSummary=()=>{};`,context);
const q={module:'cars',query_id:'old-query',requested:{start_date:'2026-09-13',end_date:'2026-09-14',limit:5},errors:[]};
context.q=q;context.error={location_options:['Florianopolis Airport (FLN), Florianopolis, Brazil','Florianopolis Downtown, Brazil']};
const picker=vm.runInContext('renderLocationChoices(q,error)',context);
const grid=picker.children.find(e=>e.attrs.role==='group');const footer=picker.children.at(-1);const go=footer.children[1];
assert(go.disabled);assert.equal(grid.children.length,2);
grid.children[0].listeners.click();assert(!go.disabled);assert.equal(grid.children[0].attrs['aria-pressed'],'true');
grid.children[1].listeners.click();assert.equal(grid.children[0].attrs['aria-pressed'],'false');
let requests=[],release;context.send=async(path,data)=>{requests.push({path,data});return new Promise(r=>release=r);};vm.runInContext('api=send',context);
(async()=>{
 const pending=go.listeners.click();await go.listeners.click();assert.equal(requests.length,1);assert.equal(requests[0].path,'/api/search');assert.equal(requests[0].data.destination,'Florianopolis Downtown, Brazil');assert.equal(requests[0].data.start,'2026-09-13');assert.equal(requests[0].data.end,'2026-09-14');assert.equal(requests[0].data.limit,5);
 release({id:'new',module:'cars',status:'running'});await pending;
 assert.equal(get('elapsed').textContent,'0min 0s');assert.equal(get('progress-title').textContent,'Consultando Carros');assert.equal(get('results-panel').hidden,true);
 const failed=vm.runInContext('renderLocationChoices(q,error)',context);const fg=failed.children.find(e=>e.attrs.role==='group'),ff=failed.children.at(-1);fg.children[0].listeners.click();context.send=async()=>{throw Error('Uma busca está em andamento.');};vm.runInContext('api=send',context);await ff.children[1].listeners.click();assert(!ff.children[1].disabled);assert.equal(ff.children[2].textContent,'Uma busca está em andamento.');assert.equal(get('results-panel').hidden,false);
 console.log('Escolha, envio, datas, clique duplo e recuperação de erro: OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
