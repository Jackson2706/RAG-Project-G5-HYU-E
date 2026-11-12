"""Archive public institutional Hanyang information; no login or access-control bypass.

Requires the project's httpx and beautifulsoup4 packages. Run from the project root.
Network failures and robots exclusions are logged; blocked hosts are not retried via aliases.
"""
from __future__ import annotations
import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

UA='HYU-Compass-Research/1.0 (public university information archival; no authenticated access)'
ROOT=Path.cwd()
MAIN='https://www.hanyang.ac.kr'
OFFICIAL_HOSTS={'book.hyu.ac','www.hyu.kr','www.ihanyang.ac.kr'}
DENY=re.compile(r'(?:login|logout|signin|signout|password|/member|/admin|admission_results|admission-results|/results|/search|/calendar\?|/board/downloadPersonal)',re.I)
FILES=re.compile(r'\.(?:jpg|jpeg|png|gif|svg|webp|ico|css|js|woff2?|ttf|mp4|mp3|zip|xlsx?|docx?|pptx?|hwp)$',re.I)

def allowed(url):
    p=urlsplit(url)
    return p.scheme in ('http','https') and not p.username and p.port in (None,80,443) and (p.hostname=='hanyang.ac.kr' or (p.hostname or '').endswith('.hanyang.ac.kr') or p.hostname in OFFICIAL_HOSTS) and not DENY.search(p.path) and not FILES.search(p.path)

def canonical(url):
    p=urlsplit(url)
    q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in ('utm_source','utm_medium','utm_campaign','fbclid','gclid','sessionid','phpsessid')]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',urlencode(sorted(q)),''))

def seeds():
    paths=['introduction','university-at-a-glance','founding-philosophy','chronology','s_college_department-info','e_college_department-info',
        'academic-calendar','course-registration','course-information','a-guide-to-your-degree','school-register-administration','grades-graduation','credit-authorization','summer-winter-school',
        'scholarships','scholarships1','dormitory','certificate-of-verification','contact-us','it-service','counseling-center','health-care-center','health-care-center1','student-id',
        'campus-map-directions','campus-map-directions1','school-bus-shuttle-bus-guide','parking-information','parking-information1','student-resources','libraries-more',
        'international-programs-seoul-','international-programs-erica-','institute-of-international-education-seoul-','institute-of-international-education-erica-','admissions-guide']
    items=[{'url':MAIN+'/web/eng/'+p,'depth':0,'campus_hint':'ERICA' if p.endswith('1') or 'erica' in p else 'SEOUL' if p in ['s_college_department-info','student-id','course-registration','counseling-center','dormitory'] else None,'topic_hint':p} for p in paths]
    items.extend({'url':'https://oia.hanyang.ac.kr'+p,'depth':0,'topic_hint':p.strip('/') or 'international_office'} for p in ['/', '/admission','/major_guidebook','/visa','/insurance','/scholarships','/counseling','/career','/forms','/contact','/sub4_01','/sub4_01/1819015','/sub4_01/1818587'])
    items.extend({'url':u,'depth':0,'campus_hint':campus,'topic_hint':'international_admissions' if 'global.' in u else 'library' if 'lib.' in u or 'information.' in u else 'housing' if 'dorm' in u else 'college_information'} for u,campus in [
        ('https://global.hanyang.ac.kr/','ERICA'),('https://eng.dormitory.hanyang.ac.kr/','SEOUL'),('https://hydorm.hanyang.ac.kr/','ERICA'),
        ('https://lib.hanyang.ac.kr/','SEOUL'),('https://information.hanyang.ac.kr/','ERICA'),('https://ericaiie.hanyang.ac.kr/','ERICA'),('https://iie.hanyang.ac.kr/','SEOUL'),
        ('https://engr.hanyang.ac.kr/','SEOUL'),('https://humanities.hanyang.ac.kr/','SEOUL'),('https://social.hanyang.ac.kr/','SEOUL'),('https://cns.hanyang.ac.kr/','SEOUL'),
        ('https://policy.hanyang.ac.kr/','SEOUL'),('https://biz.hanyang.ac.kr/','SEOUL'),('https://humanecology.hanyang.ac.kr/','SEOUL'),('https://music.hanyang.ac.kr/','SEOUL'),
        ('https://copas.hanyang.ac.kr/','SEOUL'),('https://cis.hanyang.ac.kr/','SEOUL'),('https://ieng.hanyang.ac.kr/','ERICA'),('https://computing.hanyang.ac.kr/','ERICA'),
        ('https://pharmacy.hanyang.ac.kr/','ERICA'),('https://atc.hanyang.ac.kr/','ERICA'),('https://ibusen.hanyang.ac.kr/','ERICA'),('https://idesign.hanyang.ac.kr/','ERICA'),
        ('https://sportsnarts.hanyang.ac.kr/','ERICA'),('https://www.sgs.hanyang.ac.kr/',None),('https://gsis.hanyang.ac.kr/', 'SEOUL')])
    items.extend({'url':u,'depth':0,'campus_hint':c,'topic_hint':topic,'academic_level':level,'academic_year':'2027','term':'spring'} for u,c,topic,level in [
        ('https://oia.hanyang.ac.kr/files/attach/filebox/2026/08/24/4bad55cf33436519f06a243547ec2a6e.pdf','SEOUL','admissions','undergraduate'),
        ('https://oia.hanyang.ac.kr/files/attach/filebox/2026/08/26/5698db4e4547aff8187ba031baa09257.pdf','ALL','admissions','graduate')])
    return items

class Collector:
    def __init__(self,args):
        self.args=args
        self.out=args.output
        self.raw=self.out/'raw'
        self.raw.mkdir(parents=True,exist_ok=True)
        self.records=[]
        self.robots={}
        self.lock=threading.Lock()
        self.host_locks={}
        self.host_times={}
        self.blocked=set()
        self.bytes=0
        self.pdfs=0
        self.known_hashes={hashlib.sha256(p.read_bytes()).hexdigest():p.as_posix() for p in (ROOT/'data/raw').glob('*.pdf')}
        self.known_hashes={sha: str(Path(p).relative_to(ROOT)) for sha,p in self.known_hashes.items()}

    def pace(self,host):
        with self.lock:
            lock=self.host_locks.setdefault(host,threading.Lock())
        with lock:
            delay=self.host_times.get(host,0)-time.monotonic()
            if delay>0:
                time.sleep(delay)
            self.host_times[host]=time.monotonic()+0.65

    def get(self,client,url,limit=45_000_000):
        for _ in range(6):
            if not allowed(url):
                raise ValueError('Redirect outside public official allowlist')
            self.pace(urlsplit(url).hostname)
            with client.stream('GET',url) as r:
                if r.status_code in (301,302,303,307,308):
                    url=canonical(urljoin(url,r.headers.get('location','')))
                    continue
                data=bytearray()
                for block in r.iter_bytes():
                    data.extend(block)
                    if len(data)>limit:
                        raise ValueError('Response exceeds byte limit')
                return r.status_code,url,dict(r.headers),bytes(data)
        raise ValueError('Too many redirects')

    def robots_ok(self,client,url):
        p=urlsplit(url)
        host=p.netloc
        with self.lock:
            host_lock=self.host_locks.setdefault('robots:'+host,threading.Lock())
        with host_lock:
            if host not in self.robots:
                endpoint=f'{p.scheme}://{host}/robots.txt'
                try:
                    code,final,headers,data=self.get(client,endpoint,1_000_000)
                    filename='robots-'+hashlib.sha256(endpoint.encode()).hexdigest()[:12]+'.txt'
                    (self.raw/filename).write_bytes(data)
                    parser=RobotFileParser()
                    if code==200:
                        parser.parse(data.decode('utf-8','replace').splitlines())
                        state='parsed'
                    elif code==404:
                        parser.parse([]); state='not_found'
                    else:
                        parser=None; state='unavailable_skip_host'
                    self.robots[host]={'parser':parser,'url':endpoint,'status':code,'state':state,'raw_file':filename}
                except Exception as exc:
                    self.robots[host]={'parser':None,'url':endpoint,'state':'unavailable_skip_host','error':str(exc)[:220]}
            entry=self.robots[host]
            return entry['parser'] is not None and entry['parser'].can_fetch(UA,url)

    def fetch(self,item):
        url=item['url']; host=urlsplit(url).hostname
        result={**item,'retrieved_at':datetime.now(timezone.utc).isoformat(),'source_id':hashlib.sha256(url.encode()).hexdigest()[:16]}
        links=[]
        try:
            with self.lock:
                blocked=host in self.blocked
            if blocked:
                result['status']='blocked_host_skipped'; return result,links
            with httpx.Client(timeout=httpx.Timeout(18,connect=10),headers={'User-Agent':UA,'Accept':'text/html,application/pdf;q=0.9,text/plain;q=0.5'},follow_redirects=False) as client:
                if not self.robots_ok(client,url):
                    result['status']='robots_or_robots_unavailable'; return result,links
                code,final,headers,data=self.get(client,url)
            result.update(http_status=code,final_url=final,content_type=headers.get('content-type',''),bytes=len(data))
            if code!=200:
                result['status']='http_error'
                if code in (401,403,429):
                    with self.lock: self.blocked.add(host)
                return result,links
            sha=hashlib.sha256(data).hexdigest()
            pdf=data.startswith(b'%PDF') or 'application/pdf' in result['content_type']
            if pdf:
                with self.lock:
                    if self.pdfs>=self.args.max_pdfs:
                        result['status']='pdf_limit'; return result,links
                    self.pdfs+=1
            elif 'html' not in result['content_type'] and b'<html' not in data[:1000].lower() and b'<!doctype' not in data[:1000].lower():
                result['status']='unsupported_content'; return result,links
            with self.lock:
                self.bytes+=len(data)
                if self.bytes>self.args.max_mb*1_000_000:
                    result['status']='total_byte_limit'; return result,links
            ext='.pdf' if pdf else '.html'
            stem=result['source_id']+'-'+re.sub('[^a-zA-Z0-9-]+','-',urlsplit(final).path.rstrip('/').split('/')[-1])[:65]
            filename=stem+ext
            result.update(status='downloaded',sha256=sha,source_type='pdf' if pdf else 'html')
            for field in ['last-modified','etag']:
                if field in headers: result[field.replace('-','_')]=headers[field]
            if sha in self.known_hashes:
                result['existing_raw_path']=self.known_hashes[sha]
            else:
                (self.raw/filename).write_bytes(data)
                result['raw_file']=filename
            if not pdf:
                soup=BeautifulSoup(data,'html.parser')
                result['title']=soup.title.get_text(' ',strip=True) if soup.title else ''
                result['html_language']=soup.html.get('lang') if soup.html else None
                if item['depth']<2:
                    for a in soup.find_all('a',href=True):
                        href=canonical(urljoin(final,a['href']))
                        label=a.get_text(' ',strip=True)
                        if not self.follow(href,label,item):continue
                        new={'url':href,'depth':item['depth']+1,'discovered_from':url,'link_text':label[:200]}
                        if urlsplit(href).hostname==host:
                            for field in ['campus_hint','academic_level']:
                                if item.get(field):new[field]=item[field]
                        links.append(new)
            return result,links
        except Exception as exc:
            result.update(status='fetch_error',error=f'{type(exc).__name__}: {exc}'[:300])
            return result,links

    def follow(self,url,label,parent):
        if not allowed(url) or len(url)>600:return False
        if re.search(r'login|logout|signin|write|delete|modify|password|p_p_auth|control_panel',url,re.I):return False
        p=urlsplit(url)
        if any(k in dict(parse_qsl(p.query)) for k in ['page','pageIndex','search_target','search_keyword','category_srl','sort_index','order_type']):return False
        if p.path.lower().endswith('.pdf') or 'procFileDownload' in url:
            return self.pdfs<self.args.max_pdfs and bool(re.search(r'guide|brochure|admission|handbook|모집요강|안내|요강|英|英文',label+' '+p.path,re.I)) and not re.search(r'result|합격|명단',label,re.I)
        if p.hostname=='www.hanyang.ac.kr':return p.path.startswith('/web/eng/') and 'p_p_' not in p.query
        if p.hostname=='oia.hanyang.ac.kr':
            return bool(re.fullmatch(r'/(?:admission|major[^/]*|visa|insurance|scholarships|coun[^/]*|career[^/]*|forms|contact[^/]*|sub[1-6]_\d{2})(?:/\d+)?/?',p.path))
        if p.hostname=='global.hanyang.ac.kr':
            return p.path in ('/','/index.php') or p.path.startswith(('/en/','/eng/','/english/')) or bool(re.search(r'admission|guide|scholar|housing|student|visa|insurance|life|language|English|영어|입학|기숙사',label,re.I))
        return parent['depth']==0 and bool(re.search(r'(?:^|/)(?:eng|en|english)(?:/|$)|guide|admission|curriculum|course|scholar|international|introduc',p.path+' '+label,re.I))

    def persist(self):
        manifest={'collection_started':self.started,'collection_finished':datetime.now(timezone.utc).isoformat(),'user_agent':UA,
            'limits':{'max_urls':self.args.max_urls,'max_pdfs':self.args.max_pdfs,'max_megabytes':self.args.max_mb,'depth':2},
            'robots':{host:{k:v for k,v in info.items() if k!='parser'} for host,info in self.robots.items()},
            'records':self.records,'counts':dict(Counter(r['status'] for r in self.records)),
            'source_bytes':sum(r.get('bytes',0) for r in self.records if r['status']=='downloaded'),
            'note':'Public unauthenticated snapshots only. Original bytes retained or linked by exact hash to an existing raw PDF. Failed responses are not treated as source documents.'}
        (self.out/'collection.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')

    def run(self):
        self.started=datetime.now(timezone.utc).isoformat()
        queue=deque(json.loads(self.args.seed_file.read_text()) if self.args.seed_file else seeds()); seen=set()
        with ThreadPoolExecutor(max_workers=4) as pool:
            while queue and len(self.records)<self.args.max_urls:
                batch=[]
                while queue and len(batch)<4 and len(self.records)+len(batch)<self.args.max_urls:
                    item=queue.popleft(); item['url']=canonical(item['url'])
                    if item['url'] in seen:continue
                    seen.add(item['url']); batch.append(item)
                for result,links in pool.map(self.fetch,batch):
                    self.records.append(result)
                    queue.extend(links)
                    print(f"{len(self.records):03d} {result['status']}: {result['url']} ({result.get('bytes',0)} bytes)",flush=True)
                self.persist()
        self.persist()
        print('DONE',json.dumps(dict(Counter(r['status'] for r in self.records))),flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seed-file',type=Path,help='Optional JSON list of public URL seed objects')
    ap.add_argument('--max-urls',type=int,default=200)
    ap.add_argument('--max-pdfs',type=int,default=10)
    ap.add_argument('--max-mb',type=int,default=250)
    args=ap.parse_args()
    assert not args.output.exists(),'Choose a new snapshot output directory.'
    Collector(args).run()

if __name__=='__main__':main()
