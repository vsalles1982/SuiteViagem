import ast,json,shutil,subprocess,unittest
from pathlib import Path

class SuggestionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node necessário para executar o JavaScript do navegador')
    def test_visible_list_excludes_hidden_and_inactive_modals(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scraper_carro/discovercars.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ler_sugestoes_em_lote')
        script=next(n.value for n in ast.walk(fn) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'querySelectorAll' in n.value)
        setup='''
function el(label,opts={}){return {parentElement:opts.parent||null,style:opts.style||{},getClientRects:()=>opts.empty?[]:[1],classList:{contains:c=>(opts.classes||[]).includes(c)},getAttribute:k=>k==='aria-hidden'?(opts.hidden?'true':null):label,querySelector:()=>opts.missing?null:{innerText:' Airport '}};}
const inactive=el('',{classes:['Modal-Container']}),active=el('',{classes:['Modal-Container','Modal-Container_isActive']});
const document={querySelectorAll:()=>[el('Airport'),el('Hidden',{hidden:true}),el('Inactive',{parent:inactive}),el('Active',{parent:active}),el('No text',{missing:true}),el('Invisible',{parent:el('',{style:{visibility:'hidden'}})}),el('Transparent',{style:{opacity:'0'}}),el('No box',{empty:true})]};
const getComputedStyle=e=>({display:'block',visibility:'visible',opacity:'1',...e.style});
'''
        code=setup+'console.log(JSON.stringify((new Function("document","getComputedStyle",'+json.dumps(script)+'))(document,getComputedStyle)));'
        rows=json.loads(subprocess.check_output(['node','-e',code],text=True))
        self.assertEqual(rows,[['Airport','Airport'],['Active','Airport']])
