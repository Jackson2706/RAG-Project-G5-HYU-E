"""Build the dated web extension from archived official Hanyang responses.

Run from repository root with --output NEW_STAGING_ROOT and --snapshots DIR DIR.
Requires bs4. Output is a staged data/ tree; no index is changed.
Only explicit reviewed selections enter filter_ready. Other extracted pages remain raw-only for review. Undated legacy regulations are never auto-promoted.
"""
import argparse,hashlib,json,re,shutil,sys
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup,Comment

STAMP='2026-11-12'
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def front(m):
 return '---\n'+'\n'.join(k+': '+('['+', '.join(map(str,v))+']' if isinstance(v,list) else json.dumps(str(v),ensure_ascii=False)) for k,v in m.items())+'\n---\n\n'
def clean(root):
 root=BeautifulSoup(str(root),'html.parser')
 for t in root.find_all(string=lambda s:isinstance(s,Comment)):t.extract()
 for t in root.select('script,style,nav,header,footer,form,input,button,select,textarea,iframe,noscript,svg,link,.responsive-dim,.stock-scroll-drag-guide') :t.decompose()
 # Keep row/column relationships in tables, including merged cells.
 for table in root.find_all('table'):
  grid={};rows=[]
  for ri,tr in enumerate(table.find_all('tr')):
   ci=0
   for cell in tr.find_all(['td','th'],recursive=False):
    while (ri,ci) in grid:ci+=1
    value=cell.get_text(' ',strip=True).replace('|','/')
    for dr in range(int(cell.get('rowspan',1))):
     for dc in range(int(cell.get('colspan',1))):grid[ri+dr,ci+dc]=value
    ci+=int(cell.get('colspan',1))
  if grid:
   for ri in range(max(x[0] for x in grid)+1):rows.append(' | '.join(grid.get((ri,ci),'') for ci in range(max(x[1] for x in grid)+1)))
   table.replace_with('\n\nTable rows (merged-cell labels repeated):\n'+'\n'.join(rows)+'\n\n')
 for h in [t for t in root.find_all(re.compile('^h[1-6]$')) if not t.find_parent(re.compile('^h[1-6]$'))]:h.insert_before('\n\n## '+h.get_text(' ',strip=True)+'\n\n');h.decompose()
 for b in root.select('br'):b.replace_with('\n')
 for t in root.find_all(['p','li','dt','dd','div','section','article']):t.insert_before('\n');t.insert_after('\n')
 text=root.get_text(' ',strip=False)
 lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines()]
 out=[]
 for line in lines:
  if not line or line in ('Homepage','Tab 1'):continue
  if out and out[-1]==line:continue
  out.append(line)
 return '\n\n'.join(out).strip()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--snapshots',nargs='+',type=Path,required=True);ap.add_argument('--curated',type=Path,default=Path('scripts/data/hanyang_2027_undergraduate.json'));a=ap.parse_args()
 assert not a.output.exists(),'Use a new staging directory'
 root=a.output/'data';rawroot=root/'raw'/('web_'+STAMP);active=root/'filter_ready'/('web_'+STAMP)
 for p in [rawroot,active]:p.mkdir(parents=True)
 records=[];units=[];seen=set()
 for bi,snapshot in enumerate(a.snapshots,1):
  batch=rawroot/f'batch{bi}';shutil.copytree(snapshot/'raw',batch/'raw');shutil.copy2(snapshot/'collection.json',batch/'collection.json')
  manifest=json.loads((snapshot/'collection.json').read_text())
  for item in manifest['records']:
   r=dict(item);r['batch']=bi;r['disposition']='not_downloaded'
   if r['status']=='downloaded':
    r['raw_source_path']=r.get('existing_raw_path', '').removeprefix('data/') or str((batch/'raw'/r['raw_file']).relative_to(root))
    r['disposition']='raw_only_pending_review'
    if r.get('existing_raw_path'):r['disposition']='duplicate_existing_pdf'
    elif r['source_type']=='html':
     soup=BeautifulSoup((root/r['raw_source_path']).read_bytes(),'html.parser');nodes=[]
     host=urlsplit(r['url']).hostname
     if host=='global.hanyang.ac.kr':nodes=soup.select('.sub-cnt')
     elif host=='oia.hanyang.ac.kr':nodes=soup.select('#content')
     elif host=='engr.hanyang.ac.kr':nodes=soup.select('#contents')
     elif host=='gsis.hanyang.ac.kr':
      for bad in soup.select('.journal-content-article,.hyu-fragment-layout-gridLeftAside .col-lg-3'):
       if re.search('개인정보처리방침|COPYRIGHT|이메일무단',bad.get_text()) or 'col-lg-3' in bad.get('class',[]):bad.decompose()
      nodes=soup.select('#main-content')
     else:nodes=[n for n in soup.select('.journal-content-article') if not re.search('개인정보처리방침|COPYRIGHT|이메일무단',n.get_text())]
     if not nodes:nodes=soup.select('main,article,#bo_v_con,.entry-content')
     text='\n\n'.join(clean(n) for n in nodes)
     if len(text)>80:
      r['extracted_text']=text
   records.append(r)
 def find(url):return next(r for r in records if r['status']=='downloaded' and r['url']==url)
 def add(r,title,body,topic,campus=None,level=None,**extra):
  body=body.strip();identity=sha((title+'\n'+body).encode())
  if identity in seen:return
  seen.add(identity);uid='web-'+identity[:16]
  m={'metadata_schema_version':'web-1','unit_id':uid,'title':title,'source_group':'official_hanyang_web','source_type':r['source_type'],'source_url':r['url'],'raw_source_path':r['raw_source_path'],'source_sha256':r['sha256'],'retrieved_at':r['retrieved_at'],'retrieved_on':STAMP,'document_type':'university_information','topic':topic,'topics':[topic],'scope':'campus' if campus else 'unknown','department_scope':'not_specified','college_scope':'not_specified','record_type':'source_summary','language':'en','review_status':'selected_source_checked','temporal_status':'source_undated','selection_policy':'selected_topics_not_exhaustive',**extra}
  if campus:m['campus']=campus
  if level:m['academic_level']=level;m['audience']=level
  filename=uid+'.md';p=active/filename
  note='Source snapshot collected '+STAMP+'. '
  if m['temporal_status']=='source_undated':note+='The source does not establish an effective date. Confirm changing procedures and availability with the responsible office. '
  p.write_text(front(m)+'# '+title+'\n\n## '+title+'\n\n'+body+'\n\n## Source and scope\n\n'+note+'Official source: '+r['url']+(' (PDF pages '+', '.join(map(str,extra['source_pages']))+').' if extra.get('source_pages') else '.')+'\n')
  units.append({'path':str(p.relative_to(active)),'sha256':sha(p.read_bytes()),'metadata':m,'body_sha256':sha(body.encode())});r['disposition']='selected_for_ingestion'
 # Checked undergraduate guide summaries; full OCR is review material, not active text.
 ug=find('https://oia.hanyang.ac.kr/files/attach/filebox/2026/08/24/4bad55cf33436519f06a243547ec2a6e.pdf')
 for x in json.loads(a.curated.read_text()):
  add(ug,x['title'],x['body'],x['topic'],'SEOUL','undergraduate',document_type='admission_guide',academic_year='2027',term='spring',student_category='international',admission_route='international_admissions',source_pages=x['pages'],temporal_status='explicit_admission_cycle',extraction_method='ocr_with_curated_summary',**({'fee_reference_year':'2026','fee_reference_term':'fall'} if x['topic']=='tuition' else {}))
 # Campus information: use concise checked summaries to avoid obsolete 2023 statistics,
 # transport frequencies, dated prices, and legacy immigration/insurance requirements.
 base='https://global.hanyang.ac.kr/eng/'
 selections=[
 ('s1/s1_2.php','What ERICA means and where it is','overview','Hanyang University ERICA is located in Ansan-si, Gyeonggi-do, South Korea. ERICA stands for Education-Research-Industry-Cluster at Ansan. Established in 1979, the campus emphasizes collaboration between education, research and industry. The source contains separately dated July 2023 statistics; those figures are not current enrollment counts.'),
 ('s1/s1_4.php','ERICA Office of International Affairs location','contacts','The ERICA Office of International Affairs is on the third floor of the Student Welfare Building, 55 Hanyangdaehak-ro, Sangnok-gu, Ansan-si, Gyeonggi-do, Republic of Korea. The postal code shown on the site is 15588. This is the ERICA office, distinct from the Seoul OIA office in the International Building.'),
 ('s1/s1_3.php','ERICA international admissions and exchange contacts','contacts','ERICA international admissions: studyerica@hanyang.ac.kr; +82-31-400-0791, 0794 or 0795. Outbound exchange: ericaexchange@hanyang.ac.kr. Short-term outbound programs: ericaoutgoing@hanyang.ac.kr. Inbound exchange and visiting programs: ericaincoming@hanyang.ac.kr. Summer school: hess@hanyang.ac.kr; winter school: hews@hanyang.ac.kr. Use the office matching your campus and program.'),
 ('s2/s2_1_1.php','ERICA outgoing exchange program overview','international_programs','An outgoing exchange allows eligible Hanyang students to study for a period at a partner university while paying tuition at Hanyang. Credits earned abroad may be transferred to the home university. A university partnership alone does not guarantee an exchange place: an active student-exchange agreement and balanced exchange arrangements are required. The page includes a 2023–2024 selection schedule; consult current notices for current dates.'),
 ('s3/s3_5_2.php','ERICA psychological counseling services','counseling','The ERICA international-student support site describes individual counseling with a professional counselor for psychological/emotional concerns, study and career questions, and adjustment to studying abroad. It also describes psychological testing and group screening. Consult ERICA OIA for current appointments, languages and availability.'),
 ('s3/s3_6.php','ERICA Hanmille and Hanmille Grad mentoring','student_support','ERICA OIA describes Hanmille, a peer mentoring program connecting current students with international and exchange students, including Hanmille Grad. Its purpose is adaptation to campus life and mutual cultural exchange. New international undergraduate and postgraduate students should check OIA email announcements for mentee applications. The page also describes cultural field programs and K-Movie Night; actual offerings and registration depend on current notices.'),
 ('s3/s3_7_1.php','ERICA library, cafeterias and campus services','student_services','ERICA campus facilities listed by OIA include the ERICA Academic Information Center/library, cafeterias, Shinhan Bank and postal services. The library has resource-reading areas, general reading rooms, group study rooms and lounges. Check the library website for current opening hours and reservation rules. The source also lists meal prices and opening hours without a clear effective date; those are not confirmed current prices or schedules.'),
 ('s3/s3_7_2.php','ERICA student apps and information channels','it_services','The ERICA OIA page describes Heyoung Campus for mobile student ID, attendance and academic administration; Hanyang University Library app for library accounts, electronic resources and seat reservations; and Hanyangbot for shuttle timetables, meals and books. OIA also operates social-media channels for exchange and international-student announcements. Confirm current availability through the official links on the source page.')]
 for path,title,topic,body in selections:add(find(base+path),title,body,topic,'ERICA')
 # College directory: split departments rather than applying one department tag to the entire list.
 for suffix,college in [('engineering.php','engineering'),('software.php','software')]:
  r=find('https://engr.hanyang.ac.kr/eng/depart/'+suffix);s=BeautifulSoup((root/r['raw_source_path']).read_bytes(),'html.parser')
  for node in s.select('.depart_list .list .desc'):
   h=node.find(['h3','h4']);title=h.get_text(' ',strip=True).replace('Homepage','').strip() if h else ''
   if not title:continue
   links=[f"{a.get_text(' ',strip=True)}: {a['href']}" for a in node.select('a[href]')]
   body=clean(node)+'\n\nOfficial department links: '+'; '.join(links)
   dep=re.sub(r'[^a-z0-9]+','-',re.sub(r'^(?:Department|School) of ','',title).lower()).strip('-')
   add(r,title+' at Hanyang Seoul',body,'overview','SEOUL','undergraduate',scope='department',department=dep,department_name=title,department_scope='specific_department',college=college,college_scope='specific_college',record_type='department_profile')
 # English academic descriptions only. Admissions calendars and undated scholarship
 # rules remain archived rather than silently presented as current policy.
 for r in records:
  u=r['url'];text=r.get('extracted_text','')
  if not text:continue
  selected=u in ['https://engr.hanyang.ac.kr/eng/about/vision.php','https://gsis.hanyang.ac.kr/en/about-us4','https://gsis.hanyang.ac.kr/en/academics','https://gsis.hanyang.ac.kr/en/master-s-degrees','https://gsis.hanyang.ac.kr/en/doctoral-degrees3','https://gsis.hanyang.ac.kr/en/curriculum4','https://gsis.hanyang.ac.kr/en/research-centers','https://gsis.hanyang.ac.kr/en/research-facilities']
  if not selected:continue
  if len(text)<180:continue
  title=r.get('title','Hanyang academic information').split(' - ')[0]
  gsis='gsis.' in u
  add(r,title+' — Hanyang '+('GSIS' if gsis else 'Seoul Engineering'),text,'courses' if 'curriculum' in u else 'overview','SEOUL','graduate' if gsis else 'undergraduate',scope='college',college='international-studies' if gsis else 'engineering',college_name='Graduate School of International Studies' if gsis else 'College of Engineering',college_scope='specific_college',record_type='selected_main_content',extraction_method='html_main_content',**({'degree_level':'masters'} if 'master-s-' in u else {'degree_level':'phd'} if 'doctoral-' in u else {}))
 # Counseling: select the English paragraph from the multilingual OIA page.
 r=find('https://oia.hanyang.ac.kr/counseling');text=r.get('extracted_text','');start=text.find('Hello, International students!');end=text.find('亲爱的',start)
 if start>=0:
  english=text[start:end if end>start else len(text)]
  add(r,'Seoul OIA counseling for international students',english,'counseling','SEOUL',student_category='international',extraction_method='english_section_selection')
 for r in records:r.pop('extracted_text',None)
 summary={'retrieved_on':STAMP,'raw_requests':len(records),'downloaded_responses':sum(r['status']=='downloaded' for r in records),'raw_unique_hashes':len({r['sha256'] for r in records if r['status']=='downloaded'}),'prepared_documents':len(units),'selected_source_urls':len({u['metadata']['source_url'] for u in units}),'topics':sorted({u['metadata']['topic'] for u in units}),'records':records,'units':units,'limitations':['Snapshot is broad but not exhaustive. Blocked hosts and failed requests remain logged.','Only selected checked English content enters active ingestion; other extractions require review.','Selected topics only from the scanned undergraduate guide; full PDF remains in raw, and disposable OCR was removed.','Undated visa/insurance rules, old notices, application-result lists, and expired schedules are not auto-promoted.','Metadata is available for filtering; frontend/backend filter controls are not changed.']}
 dump(root/('filter_ready.web_'+STAMP+'.manifest.json'),summary)
 dump(rawroot/'manifest.json',{'retrieved_on':STAMP,'records':records,'note':'Original public response bytes. Raw data is not an ingestion target.'})
 dump(root/('filter_ready.web_'+STAMP+'.schema.json'),{'version':'web-1','required_fields':['metadata_schema_version','unit_id','title','source_url','raw_source_path','source_sha256','retrieved_on','source_type','document_type','topic','topics','scope','language','temporal_status'],'optional_filters':['campus','academic_level','audience','student_category','academic_year','term','college','department','degree_level'],'unknown_policy':'Missing scope/date fields mean unknown, never infer ALL, a current academic year, or international status from English. retrieved_on is collection time, not academic_year/effective_date.','scope_policy':'College-wide multi-department pages omit department. General campus services omit academic_level unless explicitly scoped.','tuition_policy':'Academic year is admission cycle. fee_reference_year and fee_reference_term describe the quoted rate period.'})
 dump(root/('filter_ready.web_'+STAMP+'.vocabulary.json'),{k:sorted({str(v) for u in units for v in (u['metadata'][k] if isinstance(u['metadata'].get(k),list) else [u['metadata'].get(k)]) if v is not None}) for k in ['campus','academic_level','topic','college','department','document_type','student_category','temporal_status']})
 (active/'README.md').write_text('# Official Hanyang web extension\n\nSee `data/filter_ready.web_'+STAMP+'.manifest.json` for provenance, hashes, selections and exclusions. Original responses: `data/raw/web_'+STAMP+'`. Non-selected sources remain raw-only. Ingest the complete `data/filter_ready` directory to retain the original PDF corpus and this extension.\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ['records','units']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
