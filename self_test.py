"""Targeted negative checks for publication and data-integrity gates."""
import copy,json,tempfile
from pathlib import Path
from render import ROOT,load,render
import brochure

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
  results+=brochure_checks(td)
 return results

def brochure_checks(td):
 """Gates for the component brochure builder: the failure modes seen in the v2026 drafts."""
 results=[]
 demo=load(ROOT/'programmes/demo.json');facts=load(ROOT/'facts/demo_facts.json');man=load(ROOT/'assets/manifest.demo.json')
 def build(name,prog=None,fcts=None,mani=None,needle=None):
  prog=copy.deepcopy(prog or demo);fp,mp=td/(name+'_facts.json'),td/(name+'_manifest.json')
  mani=copy.deepcopy(mani or man);mani['base_dir']=str(ROOT/'assets')
  fp.write_text(json.dumps(fcts or facts));mp.write_text(json.dumps(mani))
  prog['facts'],prog['assets']=str(fp),str(mp);pp=td/(name+'.json');pp.write_text(json.dumps(prog))
  out=td/(name+'.pdf')
  try:
   brochure.build(pp,out);ok=needle is None and out.exists();reason='built' if ok else 'Expected rejection, got success'
  except brochure.BuildError as e:
   ok=needle is not None and needle in str(e) and not out.exists();reason=needle if ok else str(e)[:300]
  results.append({'test':'brochure_'+name,'passed':ok,'reason':reason})
 build('demo_builds')
 f=copy.deepcopy(facts);f['people']['mentor']['photo']='missing_mentor';build('mentor_photo_missing',fcts=f,needle='Missing image "missing_mentor"')
 f=copy.deepcopy(facts)
 for t in f['testimonials'].values():t['photo']='demo_mentor'
 build('same_photo_reused',fcts=f,needle='Image repetition')
 mm=copy.deepcopy(man);mm['images']['alumni_x']={'file':'demo-portrait.png','role':'portrait'};f=copy.deepcopy(facts);f['testimonials']['demo_a']['photo']='alumni_x'
 build('duplicate_photo_two_names',fcts=f,mani=mm,needle='Same photo under two names')
 p=copy.deepcopy(demo);p['pages'][1]['subtitle']='Over 900+ participants trained so far.';build('retired_fact',prog=p,needle='Retired fact "900+"')
 p=copy.deepcopy(demo);p['pages'][1]['subtitle']='Now 1,200+ participants trained.';build('conflicting_fact',prog=p,needle='Stale or conflicting figure')
 p=copy.deepcopy(demo);p['pages'][1]['subtitle']='{{fact.not_defined}}';build('unresolved_token',prog=p,needle='Unresolved token')
 p=copy.deepcopy(demo);p['pages'][1]['background']='forest';build('page_background_override',prog=p,needle='theme-locked')
 p=copy.deepcopy(demo);p['pages'][2]['blocks']=[{'type':'paragraph','text':'Only prose.'}];build('page_without_infographic',prog=p,needle='no infographic')
 p=copy.deepcopy(demo);p['pages'][1]['blocks'].append({'type':'paragraph','text':'Extended wording '*900});build('page_overflow',prog=p,needle='overflows')
 p=copy.deepcopy(demo);p['pages'][1]['subtitle']='Start date TBC';build('unfinished_marker',prog=p,needle='Unfinished content marker')
 p=copy.deepcopy(demo);p['pages'][1]['title']='A deliberately long action title that keeps going well past two lines of the page width';p['pages'][1]['title_em']='and then some more words';build('title_too_long',prog=p,needle='action title runs')
 import io,contextlib
 with contextlib.redirect_stdout(io.StringIO()):open_q=brochure.intake(ROOT/'programmes/_template.json')
 results.append({'test':'brochure_template_asks_intake_questions','passed':len(open_q)>=10,'reason':'%d open questions'%len(open_q)})
 return results

if __name__=='__main__':
 results=run();print(json.dumps(results,indent=2));assert all(r['passed'] for r in results)
