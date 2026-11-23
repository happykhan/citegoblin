"""Google transport with first-run OAuth sign-in and reusable authorisation."""
import json
from pathlib import Path
from .planning import digest, verify
from .document import Document
from .auth import private_write


class Google:
    def __init__(self):
        from .auth import credentials
        try:
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as error:
            raise ValueError('Install citegoblin[google] for Google access') from error
        self.session=AuthorizedSession(credentials())

    def _request(self, method, url, **kwargs):
        from requests import RequestException
        try:
            response=self.session.request(method,url,timeout=40,**kwargs)
        except RequestException as error:
            raise ValueError('Google connection failed; write outcome may be uncertain; no automatic retry') from error
        if not response.ok:
            # Avoid logging request headers or credential-bearing responses.
            if response.status_code in (403,404) and method=='GET' and ('/documents/'in url or '/files/'in url):
                raise ValueError('Google denied access to this file. Run citegoblin connect "GOOGLE_DOC_URL" and select it, using an account with edit/comment access. No automatic write retry.')
            raise ValueError(f'Google request failed (HTTP {response.status_code}); no automatic write retry')
        return response

    def document(self, key):
        return self._request('GET',f'https://docs.googleapis.com/v1/documents/{key}',params={'includeTabsContent':'true'}).json()

    def comments(self,key):
        rows=[];token=None
        while True:
            params={'fields':'nextPageToken,comments(id,content,anchor,createdTime,modifiedTime,resolved,deleted,quotedFileContent,author,replies(id,content,deleted,author(me)))','pageSize':100}
            if token:params['pageToken']=token
            data=self._request('GET',f'https://www.googleapis.com/drive/v3/files/{key}/comments',params=params).json()
            for comment in data.get('comments',[]):
                comment.setdefault('replies',[])
                comment['_repliesComplete']=True
                rows.append(comment)
            token=data.get('nextPageToken')
            if not token:return rows

    def comment(self,key,comment_id):
        return self._request('GET',f'https://www.googleapis.com/drive/v3/files/{key}/comments/{comment_id}',
                             params={'fields':'id,content,anchor,resolved,deleted,author(me)'}).json()

    def replies(self,key,comment_id):
        rows=[];token=None
        while True:
            params={'fields':'nextPageToken,replies(id,content,deleted,author(me))','pageSize':100}
            if token:params['pageToken']=token
            data=self._request('GET',f'https://www.googleapis.com/drive/v3/files/{key}/comments/{comment_id}/replies',params=params).json()
            rows.extend(data.get('replies',[]));token=data.get('nextPageToken')
            if not token:return rows

    def create_reply(self,key,comment_id,content):
        return self._request('POST',f'https://www.googleapis.com/drive/v3/files/{key}/comments/{comment_id}/replies',
                             params={'fields':'id,content,author(me)'},json={'content':content}).json()

    def update_reply(self,key,comment_id,reply_id,content):
        return self._request('PATCH',f'https://www.googleapis.com/drive/v3/files/{key}/comments/{comment_id}/replies/{reply_id}',
                             params={'fields':'id,content,author(me)'},json={'content':content}).json()

    def resolve_comment(self,key,comment_id):
        return self._request('POST',f'https://www.googleapis.com/drive/v3/files/{key}/comments/{comment_id}/replies',
                             params={'fields':'id,action'},
                             json={'action':'resolve','content':'CiteGoblin: command completed and verified.'}).json()

    def export_docx(self,key):
        return self._request('GET',f'https://www.googleapis.com/drive/v3/files/{key}/export',params={'mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}).content

    def batch(self,key,requests,revision):
        return self._request('POST',f'https://docs.googleapis.com/v1/documents/{key}:batchUpdate',json={'requests':requests,'writeControl':{'requiredRevisionId':revision}}).json()


def apply(client,plan,journal,*,verifier=verify):
    """Guard each batch and refuse an uncertain/incomplete previous run."""
    if verifier is verify and plan.get('schema')!='citegoblin-plan/1':raise ValueError('Unsupported edit plan; generate a new References-only cleanup plan or a citation plan')
    journal=Path(journal)
    if journal.exists():
        previous=json.loads(journal.read_text())
        if previous.get('planHash')!=digest(plan):raise ValueError('Journal belongs to another plan')
        if previous.get('complete'):
            return verifier(Document(client.document(plan['documentId']),plan['tabId']),plan)
        raise ValueError('An earlier run is incomplete; inspect live state and replan, do not replay')
    if [digest(b)for b in plan['batches']]!=plan['batchHashes']:raise ValueError('Plan batch hashes do not match')
    current=client.document(plan['documentId'])
    if current['revisionId']!=plan['revisionId']:raise ValueError('Document changed; regenerate the plan')
    state={'planHash':digest(plan),'revision':plan['revisionId'],'done':0,'inflight':None,'complete':False}
    def persist():
        private_write(journal,json.dumps(state,separators=(',',':')))
    persist()
    for i,batch in enumerate(plan['batches']):
        state['inflight']=i;persist()
        result=client.batch(plan['documentId'],batch,state['revision'])
        revision=result.get('writeControl',{}).get('requiredRevisionId')
        if not revision:raise ValueError('Write result has no revision; inspect before retrying')
        state.update({'revision':revision,'done':i+1,'inflight':None});persist()
    result=verifier(Document(client.document(plan['documentId']),plan['tabId']),plan)
    state.update({'complete':True,'verification':result});persist();return result
