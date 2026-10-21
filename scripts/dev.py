"""Run the two local processes together. No cloud actions or automatic installs."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    npm = shutil.which('npm')
    if not npm:
        sys.exit('Node.js/npm is missing. Install Node.js 22.12+ or 24 LTS, then run make install. See README.')
    if not (ROOT/'frontend/node_modules').exists():
        sys.exit('Frontend dependencies are missing. Run make install first.')
    children = []
    try:
        children.append(subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--reload','--host','127.0.0.1','--port','8000'],cwd=ROOT))
        children.append(subprocess.Popen([npm,'run','dev'],cwd=ROOT/'frontend'))
        print('Open http://127.0.0.1:5173 — API docs: http://127.0.0.1:8000/docs',flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

if __name__=='__main__':
    main()
