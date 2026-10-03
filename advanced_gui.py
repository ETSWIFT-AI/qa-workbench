"""Small launcher for the optional layer; original gui.py is unchanged."""
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox

ROOT=Path(__file__).resolve().parent

def main():
    window=tk.Tk();window.title('Advanced website assessment');window.geometry('720x330')
    box=ttk.Frame(window,padding=24);box.pack(fill='both',expand=True)
    ttk.Label(box,text='Advanced assessment — from-scratch learning',font=('Segoe UI',16,'bold')).pack(anchor='w')
    ttk.Label(box,text='Start with read-only evidence. A trained model is optional; no pretrained model is loaded.',wraplength=650).pack(anchor='w',pady=12)
    url=tk.StringVar(value='https://badssl.com/');model=tk.StringVar()
    ttk.Label(box,text='Website URL').pack(anchor='w');ttk.Entry(box,textvariable=url,width=85).pack(fill='x')
    ttk.Label(box,text='Optional trained model folder (leave blank before training)').pack(anchor='w',pady=(12,0));ttk.Entry(box,textvariable=model,width=85).pack(fill='x')
    def start():
        from advanced import __version__
        import importlib.util
        if not importlib.util.find_spec('playwright'):messagebox.showerror('Setup','Run setup_windows.bat first.');return
        command=[sys.executable,str(ROOT/'advanced.py'),'scan',url.get().strip()]
        if model.get().strip():command+=['--model',model.get().strip()]
        try:
            subprocess.Popen(command,cwd=ROOT,creationflags=subprocess.CREATE_NEW_CONSOLE if os.name=='nt' else 0)
            messagebox.showinfo('Scan started','The scan runs in its console. It prints the report path when finished. Reports are saved in the reports folder.')
        except Exception as exc:messagebox.showerror('Unable to start',str(exc))
    ttk.Button(box,text='Start read-only scan',command=start).pack(anchor='w',pady=20);window.mainloop()
if __name__=='__main__':main()
