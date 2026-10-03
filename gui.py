"""Local desktop launcher and test builder. No web server or extra GUI package."""
import json
import os
import signal
import queue
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from qa.guided import age_rule,navigation_rule,api_rule,save_config
from qa.history import dashboard

ROOT=Path(__file__).resolve().parent

class App:
    def __init__(self,window):
        self.window=window;window.title('Website QA 3 — quality and coverage');window.geometry('970x740')
        self.queue=queue.Queue();self.process=None;self.latest=None;self.cfg={};self.running=False;self.demo_process=None
        self.url=tk.StringVar(value='http://127.0.0.1:8765')
        self.mode=tk.StringVar(value='Read-only')
        self.profile=tk.StringVar(value='Standard: desktop + mobile')
        self.config_path=tk.StringVar();self.actions=tk.BooleanVar();self.auto=tk.BooleanVar(value=True)
        self.explore=tk.BooleanVar();self.zap=tk.BooleanVar();self.crux_env=tk.StringVar()
        wrapper=ttk.Frame(window,padding=20);wrapper.pack(fill='both',expand=True)
        ttk.Label(wrapper,text='Website QA',font=('Segoe UI',24,'bold')).pack(anchor='w')
        ttk.Label(wrapper,text='A high tested-quality score is not release approval. Always check coverage.').pack(anchor='w',pady=(0,15))
        notebook=ttk.Notebook(wrapper);notebook.pack(fill='both',expand=True)
        scan=ttk.Frame(notebook,padding=12);builder=ttk.Frame(notebook,padding=12)
        notebook.add(scan,text='Run a scan');notebook.add(builder,text='Build tests without JSON')
        self.row(scan,'Website URL',ttk.Entry(scan,textvariable=self.url,width=75))
        self.row(scan,'Profile',ttk.Combobox(scan,textvariable=self.profile,state='readonly',values=['Quick: desktop only','Standard: desktop + mobile','Full matrix: 3 browsers × 3 viewports'],width=48))
        self.row(scan,'Mode',ttk.Combobox(scan,textvariable=self.mode,state='readonly',values=['Read-only','Staging: actions enabled'],width=48))
        ttk.Checkbutton(scan,text='I authorize state-changing tests on this target and have disposable test data.',variable=self.actions).pack(anchor='w',pady=6)
        ttk.Checkbutton(scan,text='Check declared HTML field boundaries in staging mode',variable=self.auto).pack(anchor='w')
        ttk.Checkbutton(scan,text='Explore buttons and SPA states in staging mode (bounded)',variable=self.explore).pack(anchor='w')
        ttk.Checkbutton(scan,text='Run ZAP baseline in staging mode (Docker required; passive rules)',variable=self.zap).pack(anchor='w')
        self.row(scan,'Optional rules',ttk.Entry(scan,textvariable=self.config_path,width=65))
        ttk.Button(scan,text='Choose rules file',command=self.choose_config).pack(anchor='w')
        self.row(scan,'Optional CrUX key env name',ttk.Entry(scan,textvariable=self.crux_env,width=35))
        buttons=ttk.Frame(scan);buttons.pack(fill='x',pady=12)
        for text,action in [('Start scan',self.start),('Stop',self.stop),('Open report',self.open_report),('Run history',self.open_history),('Start local demo',self.demo)]: ttk.Button(buttons,text=text,command=action).pack(side='left',padx=3)
        self.status=tk.StringVar(value='Ready. Use the local demo first.');ttk.Label(scan,textvariable=self.status,wraplength=870).pack(anchor='w')
        self.log=tk.Text(scan,height=10,wrap='word');self.log.pack(fill='both',expand=True,pady=8)
        ttk.Label(builder,text='These recipes ask you for expected outcomes; they do not invent business rules.',wraplength=800).pack(anchor='w',pady=8)
        for text,action in [('Add navigation test',self.add_navigation),('Add integer age boundary test',self.add_age),('Add API status test',self.add_api),('Load existing rules',self.load_rules),('Save rules and use for scan',self.save_rules)]: ttk.Button(builder,text=text,command=action).pack(anchor='w',pady=5)
        self.tests=tk.Listbox(builder,height=14,width=110);self.tests.pack(fill='both',expand=True,pady=8)
        ttk.Button(builder,text='Remove selected test',command=self.remove_test).pack(anchor='w')
        window.after(150,self.poll);window.protocol('WM_DELETE_WINDOW',self.close)

    def row(self,parent,label,widget):
        frame=ttk.Frame(parent);frame.pack(fill='x',pady=4)
        ttk.Label(frame,text=label,width=28).pack(side='left');widget.pack(in_=frame,side='left',fill='x',expand=True)
    def ask(self,label,default=''):
        value=simpledialog.askstring('Test builder',label,initialvalue=default,parent=self.window)
        if value is None: raise InterruptedError()
        return value.strip()
    def add_navigation(self):
        try:
            r=navigation_rule(self.ask('Test name'),self.ask('Starting path','/'),self.ask('Button or link CSS selector, e.g. #continue'),self.ask('Expected destination path','/about'))
            self.cfg.setdefault('journeys',[]).append(r);self.refresh()
        except InterruptedError: pass
        except Exception as e: messagebox.showerror('Invalid test',str(e))
    def add_age(self):
        try:
            r=age_rule(self.ask('Test name'),self.ask('Form path','/register'),self.ask('Age selector','#age'),self.ask('Minimum age','18'),self.ask('Maximum age','120'))
            self.cfg.setdefault('fields',[]).append(r);self.refresh()
        except InterruptedError: pass
        except Exception as e: messagebox.showerror('Invalid test',str(e))
    def add_api(self):
        try:
            r=api_rule(self.ask('Test name'),self.ask('Endpoint path','/api/profile'),self.ask('Expected HTTP status','401'))
            self.cfg.setdefault('api_tests',[]).append(r);self.refresh()
        except InterruptedError: pass
        except Exception as e: messagebox.showerror('Invalid test',str(e))
    def refresh(self):
        self.tests.delete(0,'end');self.index=[]
        for family in ('journeys','fields','api_tests'):
            for i,r in enumerate(self.cfg.get(family,[])): self.tests.insert('end',family+': '+r['name']);self.index.append((family,i))
    def remove_test(self):
        if self.tests.curselection():
            family,i=self.index[self.tests.curselection()[0]];self.cfg[family].pop(i);self.refresh()
    def load_rules(self):
        p=filedialog.askopenfilename(filetypes=[('JSON rules','*.json')])
        if p:
            try: self.cfg=json.loads(Path(p).read_text());self.refresh();self.config_path.set(p)
            except Exception as e: messagebox.showerror('Cannot load rules',str(e))
    def save_rules(self):
        p=filedialog.asksaveasfilename(defaultextension='.json',initialfile='my-rules.json')
        if p:
            try: save_config(p,self.cfg,self.url.get());self.config_path.set(p);messagebox.showinfo('Saved','Rules saved and selected for the next scan.')
            except Exception as e: messagebox.showerror('Invalid configuration',str(e))
    def choose_config(self):
        p=filedialog.askopenfilename(filetypes=[('JSON rules','*.json')])
        if p: self.config_path.set(p)
    def start(self):
        if self.running: return
        staging=self.mode.get().startswith('Staging')
        if staging and not self.actions.get(): messagebox.showerror('Authorization needed','Tick the staging authorization box before enabling actions.');return
        if (self.explore.get() or self.zap.get()) and not staging: messagebox.showerror('Choose staging mode','Exploration and ZAP crawling require action-enabled staging mode.');return
        self.latest=ROOT/'reports'/('run-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        args=[sys.executable,'-u',str(ROOT/'tester.py'),self.url.get(),'--output',str(self.latest)]
        if self.profile.get().startswith('Quick'):args+=['--max-pages','3','--repeats','1','--viewports','desktop']
        elif self.profile.get().startswith('Full'):args+=['--browsers','chromium,firefox,webkit','--viewports','desktop,mobile,tablet','--max-seconds','1800']
        if staging:args+=['--allow-actions']
        if staging and self.auto.get():args+=['--auto-fields']
        if self.explore.get():args+=['--explore-actions']
        if self.zap.get():args+=['--zap-baseline']
        if self.config_path.get():args+=['--config',self.config_path.get()]
        if self.crux_env.get():args+=['--crux-key-env',self.crux_env.get()]
        self.running=True
        self.log.delete('1.0','end');self.status.set('Running… progress appears below. Missing tests will remain coverage gaps.')
        def worker():
            try:
                self.process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',start_new_session=(os.name!='nt'))
                for line in self.process.stdout:self.queue.put(('log',line))
                self.queue.put(('done',self.process.wait()))
            except Exception as e:self.queue.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.queue.get_nowait()
                if kind=='log':self.log.insert('end',value);self.log.see('end')
                elif kind=='done':
                    self.running=False
                    p=self.latest/'report.json'
                    if p.is_file():
                        s=json.loads(p.read_text())['score'];self.status.set(f"Finished. Tested quality: {s['score'] if s['score'] is not None else 'N/A'} | Coverage: {s['coverage']}% | {s['gate']} | Exit {value}")
                    else:self.status.set('Stopped or failed before report creation; inspect the log.')
                else:self.running=False;self.status.set(value)
        except queue.Empty:pass
        self.window.after(150,self.poll)
    def stop(self):
        if self.process and self.process.poll() is None:
            if os.name=='nt': subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],capture_output=True)
            else:
                try: os.killpg(self.process.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            self.status.set('Stopping scan. An interrupted run may have no complete report.')
    def open_report(self):
        if self.latest and (self.latest/'report.html').is_file():webbrowser.open((self.latest/'report.html').as_uri())
        else:messagebox.showinfo('No report','Run a scan first, or open sample-report/report.html.')
    def open_history(self):
        try:
            output=ROOT/'reports/history.html';dashboard(ROOT/'reports/history.sqlite3',output);webbrowser.open(output.as_uri())
        except Exception as e:messagebox.showinfo('History unavailable',str(e))
    def demo(self):
        if self.demo_process is None or self.demo_process.poll() is not None:
            self.demo_process=subprocess.Popen([sys.executable,str(ROOT/'examples/demo_site.py')],cwd=ROOT)
        self.url.set('http://127.0.0.1:8765');self.config_path.set(str(ROOT/'examples/demo-rules.json'));messagebox.showinfo('Demo','Demo launched on port 8765. Choose staging mode and authorize test actions to run its workflows.')
    def close(self):
        self.stop()
        if self.demo_process and self.demo_process.poll() is None:self.demo_process.terminate()
        self.window.destroy()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
