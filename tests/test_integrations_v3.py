import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa.core import Report
from qa.security import zap_baseline

class Process:
    def __init__(self,code):self.returncode=code
    async def wait(self):return self.returncode

class IntegrationAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_zap_warning_exit_with_new_report_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);r=Report('https://example.com',{})
            async def launch(*cmd,**kwargs):
                self.assertEqual(cmd[:2],('docker','run'))
                self.assertIn('zap-baseline.py',cmd)
                (out/'zap/zap.json').write_text(json.dumps({'site':[{'@name':'https://example.com','alerts':[]}]}))
                return Process(2)
            with patch('qa.security.asyncio.create_subprocess_exec',side_effect=launch):
                path=await zap_baseline('https://example.com',out,r)
            self.assertTrue(path.is_file());self.assertFalse(r.results)

    async def test_stale_zap_report_cannot_mask_failed_execution(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'zap').mkdir();(out/'zap/zap.json').write_text('{}')
            r=Report('https://example.com',{})
            async def launch(*args,**kwargs):return Process(0)
            with patch('qa.security.asyncio.create_subprocess_exec',side_effect=launch):
                result=await zap_baseline('https://example.com',out,r)
            self.assertIsNone(result);self.assertEqual(r.results[0]['status'],'ERROR')

if __name__=='__main__':unittest.main()
