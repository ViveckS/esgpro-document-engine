"""Targeted negative checks for publication and data-integrity gates."""
import copy,json,tempfile
from pathlib import Path
from render import ROOT,load,render

def run():
 m=load(ROOT/'models/demo_content.json');b=load(ROOT/'brand_config.json');l=load(ROOT/'layouts/demo.json');results=[]
 with tempfile.TemporaryDirectory() as td:
  td=Path(td)
  def check(name,model,brand,layout,needle,final=False):
   for fn,obj in [('m.json',model),('b.json',brand),('l.json',layout)]:(td/fn).write_text(json.dumps(obj))
   out=td/(name+'.pdf')
   try:render(td/'m.json',td/'b.json',td/'l.json',out,final);results.append({'test':name,'passed':False,'reason':'Expected rejection, got success'})
   except ValueError as e:results.append({'test':name,'passed':needle in str(e) and not out.exists(),'reason':needle})
  check('final_release_with_open_issues',m,b,l,'Open content issues',True)
  n=copy.deepcopy(m);key=next(k for k,v in n['blocks'].items() if '100' in v['rich_text']);n['blocks'][key]['rich_text']=n['blocks'][key]['rich_text'].replace('100','101');check('unapproved_numerical_change',n,b,l,'Numeric change')
  n=copy.deepcopy(m);key=next(e['content_id'] for e in l['pages'][0]['elements'] if e['type']=='text' and e['max_height']<50);n['blocks'][key]['rich_text']='Extended wording '*600;n['blocks'][key]['locked_numeric_tokens']=[];check('long_copy_overflow',n,b,l,'text overflow')
  n=copy.deepcopy(b);n['fonts']['Sans']='fonts/not-supplied.ttf';check('missing_font_no_substitution',m,n,l,'Missing font')
  n=copy.deepcopy(b);n['logos']['primary']=None;check('required_logo_missing',m,n,l,'Required primary logo')
  check('blank_programme_not_publishable',load(ROOT/'models/new_programme_skeleton.json'),b,l,'Unfilled content slot')
 return results
if __name__=='__main__':
 results=run();print(json.dumps(results,indent=2));assert all(r['passed'] for r in results)
