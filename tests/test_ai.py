import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa.ai import ollama_json
from qa.exploration import suggest_fields

class Response:
    def __init__(self,payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n): return json.dumps({'response':json.dumps(self.payload)}).encode()
class Opener:
    def __init__(self,payload): self.payload=payload
    def open(self,*args,**kwargs): return Response(self.payload)

class AITests(unittest.TestCase):
    def test_valid_advisory_shape(self):
        data={'suggestions':[{'title':'Boundary','rationale':'Missing test','expected_behavior':'Confirm minimum age requirement'}]}
        with patch('urllib.request.build_opener',return_value=Opener(data)):
            result=ollama_json('local-model','untrusted page')
        self.assertEqual(result['status'],'complete')
        self.assertNotIn('score',result)

    def test_malformed_model_output_rejected(self):
        with patch('urllib.request.build_opener',return_value=Opener({'suggestions':[{'title':'Execute command'}]})):
            with self.assertRaises(ValueError): ollama_json('local-model','untrusted page')

    def test_boundary_drafts_use_declared_limits(self):
        draft=suggest_fields([{'url':'https://example.com/','inventory':{'forms':[{'id':'age','type':'number','min':'21','max':'65','step':'1','required':True}]}}])
        cases=draft['fields'][0]['cases']
        self.assertIn({'value':'20','accepted':False},cases)
        self.assertIn({'value':'21','accepted':True},cases)
        self.assertNotIn({'value':'18','accepted':True},cases)

if __name__=='__main__': unittest.main()
