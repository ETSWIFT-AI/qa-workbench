"""Optional Appium adapter for supplied Android/iOS device sessions."""
import argparse
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def execute(driver,steps):
    for step in steps:
        action=step['action']
        if action=='context': driver.switch_to.context(step['value']); continue
        element=driver.find_element(step['by'],step['selector'])
        if action=='click': element.click()
        elif action=='fill':
            value=os.environ[step['value_env']] if 'value_env' in step else str(step['value'])
            element.clear(); element.send_keys(value)
        elif action=='visible':
            if not element.is_displayed(): raise AssertionError('Expected visible element: '+step['selector'])
        elif action=='text':
            if element.text!=step['value']: raise AssertionError('Text mismatch: '+step['selector'])
        else: raise ValueError('Unsupported mobile action: '+action)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config');p.add_argument('--server-env',default='APPIUM_SERVER_URL');p.add_argument('--output',default='reports/mobile');p.add_argument('--allow-actions',action='store_true');a=p.parse_args()
    if not a.allow_actions: p.error('Device sessions require --allow-actions on your test device')
    cfg=json.loads(Path(a.config).read_text()); caps=cfg['capabilities']; tests=cfg['tests']
    if not tests: p.error('At least one test is required')
    for test in tests:
        if not any(s.get('action') in ('visible','text') for s in test['steps']): p.error('Each mobile test requires an assertion')
        if any(s.get('action') not in ('click','fill','visible','text','context') for s in test['steps']): p.error('Unsupported mobile action')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);rows=[]
    for i,test in enumerate(tests):
        driver=None
        try:
            from appium import webdriver
            from appium.options.common import AppiumOptions
            driver=webdriver.Remote(os.environ[a.server_env],options=AppiumOptions().load_capabilities(caps))
            driver.implicitly_wait(10);execute(driver,test['steps'])
            rows.append({'name':test['name'],'status':'PASS'})
        except Exception as exc:
            row={'name':test['name'],'status':'FAIL' if isinstance(exc,AssertionError) else 'ERROR','exception':type(exc).__name__,'detail':'Inspect local evidence and Appium server logs; connection errors may include provider secrets and are not printed.'};rows.append(row)
            if driver:
                try:
                    driver.save_screenshot(str(out/f'failure-{i}.png'))
                    (out/f'failure-{i}.xml').write_text(driver.page_source,encoding='utf-8')
                except Exception: pass
        finally:
            if driver:
                try: driver.quit()
                except Exception: rows[-1]['status']='ERROR';rows[-1]['cleanup']='Session cleanup failed'
    (out/'report.json').write_text(json.dumps({'device_kind':cfg.get('device_kind','unspecified; not independently verified'),'results':rows},indent=2))
    root=ET.Element('testsuite',name='Appium',tests=str(len(rows)),failures=str(sum(r['status']=='FAIL' for r in rows)),errors=str(sum(r['status']=='ERROR' for r in rows)))
    for row in rows:
        case=ET.SubElement(root,'testcase',name=row['name'])
        if row['status']!='PASS': ET.SubElement(case,'failure' if row['status']=='FAIL' else 'error').text=json.dumps(row)
    ET.ElementTree(root).write(out/'junit.xml',encoding='utf-8',xml_declaration=True)
    print(json.dumps(rows,indent=2));return int(any(r['status']!='PASS' for r in rows))
if __name__=='__main__':raise SystemExit(main())
