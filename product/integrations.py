"""Explicitly approved issue creation. No automatic publishing or retries."""
import base64
import hashlib
import json
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('Redirect refused; credentials were not forwarded')

def prepare(provider,title,body,repository='',server='',project='',email='',issue_type='Bug'):
    if not title or len(title)>250 or len(body)>50000:raise ValueError('Issue title/body missing or too large')
    if provider=='github':
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Repository must be owner/name')
        return {'provider':provider,'url':'https://api.github.com/repos/'+repository+'/issues','payload':{'title':title,'body':body},'identity':repository}
    if provider!='jira':raise ValueError('Unknown provider')
    p=urlsplit(server)
    if p.scheme!='https' or not p.hostname or not re.fullmatch(r'[a-z0-9-]+\.atlassian\.net',p.hostname) or p.username or p.password or p.port or p.path not in ('','/') or p.query or p.fragment:
        raise ValueError('Use a Jira Cloud origin such as https://your-team.atlassian.net')
    if not re.fullmatch('[A-Z][A-Z0-9_]*',project) or '@' not in email:raise ValueError('Jira project key and account email required')
    if not issue_type or len(issue_type)>100:raise ValueError('Invalid issue type')
    adf={'type':'doc','version':1,'content':[{'type':'paragraph','content':[{'type':'text','text':line or ' '}]} for line in body.splitlines()]}
    return {'provider':provider,'url':server.rstrip('/')+'/rest/api/3/issue','payload':{'fields':{'project':{'key':project},'summary':title,'description':adf,'issuetype':{'name':issue_type}}},'identity':server.rstrip('/')+'/'+project,'email':email}

def digest(preview):return hashlib.sha256(json.dumps(preview,sort_keys=True).encode()).hexdigest()

def publish(preview,token,confirmed_digest,opener=None):
    if not token:raise ValueError('Missing API token')
    if confirmed_digest!=digest(preview):raise ValueError('Preview changed or confirmation digest missing; review the exact preview first')
    headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'QA-Workbench-Beta'}
    if preview['provider']=='github':headers['Authorization']='Bearer '+token
    else:headers['Authorization']='Basic '+base64.b64encode((preview['email']+':'+token).encode()).decode()
    request=Request(preview['url'],data=json.dumps(preview['payload']).encode(),headers=headers,method='POST')
    try:
        with (opener or build_opener(NoRedirect())).open(request,timeout=20) as response:
            if response.status!=201:raise RuntimeError('Provider did not confirm issue creation')
            data=json.loads(response.read(2_000_000))
    except HTTPError as exc:raise RuntimeError('Provider returned HTTP '+str(exc.code)+'; check token permissions and project-required fields. No automatic retry.') from None
    if preview['provider']=='github':
        number=data.get('number')
        if not isinstance(number,int):raise RuntimeError('Unexpected provider response; check provider before retrying')
        return 'https://github.com/'+preview['identity']+'/issues/'+str(number)
    key=data.get('key','')
    if not re.fullmatch('[A-Z][A-Z0-9_]*-[0-9]+',key):raise RuntimeError('Unexpected provider response; check provider before retrying')
    return preview['url'].split('/rest/')[0]+'/browse/'+key
