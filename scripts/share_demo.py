"""Share a key-free planner for recording through a free, one-hour HTTPS tunnel."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
CACHE=ROOT/'.cache'
REPO='j-stoerk/nebiusxnvidia_hackathon'


def stop(process):
    """Windows virtualenv launchers may own a child interpreter; stop both."""
    if process is None or process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:process.terminate()
    process.wait(timeout=10)


def publish_session(info):
    """Update the public recording link, using the existing GitHub login."""
    endpoint=f'repos/{REPO}/contents/live.json'
    current=subprocess.run(['gh','api',endpoint+'?ref=gh-pages'],capture_output=True,text=True)
    body={'message':'Update the live recording session','branch':'gh-pages',
          'content':base64.b64encode(json.dumps(info,indent=2).encode()).decode()}
    if current.returncode==0:body['sha']=json.loads(current.stdout)['sha']
    payload=CACHE/'publish-live-link.json';payload.write_text(json.dumps(body))
    result=subprocess.run(['gh','api',endpoint,'--method','PUT','--input',str(payload)],capture_output=True,text=True)
    if result.returncode:print('Live URL works; public page link was not updated. Check gh authentication.',flush=True)
    else:print('Public entry: https://j-stoerk.github.io/nebiusxnvidia_hackathon/live.html',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8025)
    parser.add_argument('--publish',action='store_true',help='Refresh the GitHub Pages recording link')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Choose a port from 1024 to 65535')
    ssh,generate=shutil.which('ssh'),shutil.which('ssh-keygen')
    if not ssh or not generate:raise SystemExit('Install OpenSSH before sharing the demo')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',args.port))==0:raise SystemExit('Port occupied; choose another --port')
    from scripts.run_demo import build_frontend
    build_frontend();CACHE.mkdir(exist_ok=True)
    key=CACHE/'demo_tunnel_key'
    if not key.exists():subprocess.run([generate,'-q','-t','ed25519','-N','','-C','chargewise-demo','-f',str(key)],check=True)
    # Public recording mode never loads a paid model credential or local inference host.
    env={**os.environ,'CLOUD_INFERENCE_ENABLED':'false','NEBIUS_API_KEY':'','HF_TOKEN':'',
         'NEMOTRON_BASE_URL':'','NEMOTRON_MODEL':''}
    tunnel=None
    with (CACHE/'shared-demo-server.log').open('w',encoding='utf-8') as log:
        app=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1',
                              '--port',str(args.port),'--workers','1','--proxy-headers','--forwarded-allow-ips','127.0.0.1'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(60):
                if app.poll() is not None:raise RuntimeError('Planner stopped; inspect .cache/shared-demo-server.log')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/health',timeout=1) as response:health=json.load(response)
                    assert health['agent']['mode']=='local_summary'
                    break
                except OSError:time.sleep(.25)
            else:raise RuntimeError('Planner did not become healthy')
            command=[ssh,'-4','-T','-p','443','-i',str(key),'-o','IdentitiesOnly=yes','-o','PreferredAuthentications=publickey',
                     '-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o',f'UserKnownHostsFile={CACHE/"pinggy-hosts"}',
                     '-o','ConnectTimeout=15','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
                     '-o','ExitOnForwardFailure=yes','-R',f'0:127.0.0.1:{args.port}','free@free.pinggy.io']
            started=datetime.now(timezone.utc)
            tunnel=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            saved=False;recent=[]
            for line in tunnel.stdout:
                recent=(recent+[line.strip()])[-6:]
                found=re.search(r'https://[a-z0-9-]+\.free\.pinggy\.net',line)
                if found and not saved:
                    saved=True
                    info={'url':found.group(),'started_at':started.isoformat(),'expires_at':(started+timedelta(minutes=59)).isoformat(),
                          'mode':'recording','inference':'local_summary'}
                    (CACHE/'shared-demo.json').write_text(json.dumps(info,indent=2))
                    print(f'Live planner: {info["url"]}\nKeep this process and laptop running while recording. Free sessions last one hour.\nPress Ctrl+C to stop. Model API calls are disabled.',flush=True)
                    if args.publish:publish_session(info)
            if not saved:raise RuntimeError('No tunnel URL received: '+'; '.join(recent))
            print('Recording session ended. Run the same command for a fresh URL.',flush=True)
        except KeyboardInterrupt:pass
        finally:
            stop(tunnel);stop(app)


if __name__=='__main__':main()
