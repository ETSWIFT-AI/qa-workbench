import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from product.server import Application,make_server
from product.recorder import SCRIPT
from examples.company_demo import make_server as demo_server

@unittest.skipUnless(os.environ.get('QA_PRODUCT_BROWSER_TESTS')=='1','Opt in to local browser integration tests')
class BrowserProductTests(unittest.TestCase):
    def test_dashboard_login_project_workflow_and_report(self):
        from playwright.sync_api import sync_playwright,expect
        with tempfile.TemporaryDirectory() as td:
            app=Application(td);app.store.create_user('admin','Strong-admin-123','admin')
            server=make_server(app,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch();page=browser.new_page(viewport={'width':1400,'height':1100})
                    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.fill('#username','admin');page.fill('#password','Strong-admin-123');page.get_by_role('button',name='Sign in',exact=True).click();page.locator('#app').wait_for(state='visible')
                    page.fill('#projectName','Example staging');page.fill('#projectUrl','https://example.test/');page.get_by_role('button',name='Create project',exact=True).click()
                    expect(page.locator('#target')).to_have_text('https://example.test/')
                    page.locator('[data-tab=workflows]').click();page.fill('#workflowName','Welcome text')
                    step=page.locator('.step').first;step.locator('select').select_option('text');step.locator('input').nth(0).fill('h1');step.locator('input').nth(1).fill('Welcome')
                    page.click('#saveWorkflow');expect(page.locator('#message')).to_contain_text('Workflow saved')
                    self.assertEqual(page.locator('#savedWorkflows button').count(),1)
                    page.locator('[data-tab=team]').click();page.fill('#newUser','viewer');page.fill('#newPassword','Strong-viewer-123');page.click('#createUser');expect(page.locator('#message')).to_contain_text('User created')
                    page.fill('#member','viewer');page.click('#grant');expect(page.locator('#message')).to_contain_text('access granted')
                    artifact=Path(os.environ.get('QA_PRODUCT_SCREENSHOT_DIR',td));artifact.mkdir(parents=True,exist_ok=True)
                    page.locator('[data-tab=overview]').click();page.screenshot(path=str(artifact/'dashboard.png'),full_page=True)
                    self.assertFalse(errors,errors);browser.close()
            finally:server.shutdown();server.server_close();thread.join()
    def test_dashboard_job_runs_existing_scanner(self):
        import time
        demo=demo_server(0);demo_thread=threading.Thread(target=demo.serve_forever,daemon=True);demo_thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                app=Application(td);uid=app.store.create_user('admin','Strong-admin-123','admin');user={'id':uid,'role':'admin'}
                pid=app.store.add_project(user,'Fixture',f'http://127.0.0.1:{demo.server_port}')
                jid=app.jobs.submit(user,pid,'scan')
                deadline=time.monotonic()+90
                while app.jobs.queue.unfinished_tasks and time.monotonic()<deadline:time.sleep(.1)
                if app.jobs.queue.unfinished_tasks:
                    app.jobs.stop(user,jid);self.fail('Scan exceeded integration-test deadline')
                report=app.run_report(user,jid)
                self.assertEqual(report['target'],f'http://127.0.0.1:{demo.server_port}/')
                self.assertTrue(report['results']);self.assertIn('score',report)
                self.assertTrue(any(f.endswith('report.html') for f in app.jobs.files(user,jid)))
        finally:demo.shutdown();demo.server_close();demo_thread.join()
    def test_recorder_does_not_collect_typed_values(self):
        from playwright.sync_api import sync_playwright,expect
        server=demo_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch();context=browser.new_context();events=[]
                context.expose_binding('qaRecord',lambda source,event:events.append(event));context.add_init_script(SCRIPT)
                page=context.new_page();page.goto(f'http://127.0.0.1:{server.server_port}')
                page.fill('#run','private-input-not-for-recording');page.fill('#item','Keyboard');page.click('#place');page.wait_for_timeout(300)
                self.assertTrue(any(e['action']=='fill' for e in events));self.assertTrue(any(e['action']=='click' for e in events))
                self.assertNotIn('private-input-not-for-recording',json.dumps(events));self.assertNotIn('Keyboard',json.dumps(events))
                page.on('dialog',lambda d:d.accept('Confirmed'));page.locator('#status').click(modifiers=['Alt']);page.wait_for_timeout(100)
                self.assertTrue(any(e['action']=='text' and e['value']=='Confirmed' for e in events));browser.close()
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
