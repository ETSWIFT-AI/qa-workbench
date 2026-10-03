import json
import unittest
from product.integrations import prepare,digest,publish,NoRedirect
class IntegrationTests(unittest.TestCase):
    def test_approval_required_before_network(self):
        p=prepare('github','Title','Body',repository='owner/repo')
        with self.assertRaises(ValueError):publish(p,'secret','wrong')
    def test_github_payload_and_url(self):
        p=prepare('github','Title','Body',repository='owner/repo')
        class Response:
            status=201
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return b'{"number":12}'
        class Opener:
            def open(self,request,timeout):
                assert request.full_url=='https://api.github.com/repos/owner/repo/issues'
                assert json.loads(request.data)=={'title':'Title','body':'Body'}
                return Response()
        self.assertEqual(publish(p,'secret',digest(p),Opener()),'https://github.com/owner/repo/issues/12')
    def test_jira_uses_adf_and_rejects_foreign_hosts(self):
        p=prepare('jira','Title','Body',server='https://team.atlassian.net',project='QA',email='qa@example.test')
        self.assertEqual(p['payload']['fields']['description']['type'],'doc')
        with self.assertRaises(ValueError):prepare('jira','Title','Body',server='https://evil.test',project='QA',email='qa@example.test')
        with self.assertRaises(RuntimeError):NoRedirect().redirect_request(None,None,None,None,None,None)
if __name__=='__main__':unittest.main()
