"""Start the local QA beta dashboard. First launch creates an administrator."""
import argparse
import getpass
from pathlib import Path
import webbrowser
from product.server import Application,make_server

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',default='product-data');p.add_argument('--port',type=int,default=8790);p.add_argument('--no-open',action='store_true');a=p.parse_args()
    app=Application(a.data_dir)
    with app.store.db() as db:exists=db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
    if not exists:
        print('Create a local administrator. Password is hashed; use at least 12 characters.')
        name=input('Username: ').strip();password=getpass.getpass('Password: ')
        if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords differ')
        app.store.create_user(name,password,'admin');del password
    server=make_server(app,a.port);url=f'http://127.0.0.1:{server.server_port}'
    print('Dashboard: '+url+'\nKeep this terminal open. Ctrl+C stops the dashboard.',flush=True)
    if not a.no_open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:
        with app.jobs.lock:
            if app.jobs.process:app.jobs.terminate(app.jobs.process)
    finally:server.server_close()
if __name__=='__main__':main()
