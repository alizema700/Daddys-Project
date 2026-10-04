import os,subprocess
from playwright.sync_api import sync_playwright
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'frames')
os.makedirs(D,exist_ok=True)
html=open(os.path.dirname(os.path.abspath(__file__))+'/prob_live_demo.html').read()
FPS=30;N=60*FPS
with sync_playwright() as p:
  b=p.chromium.launch(); pg=b.new_page(viewport={'width':1920,'height':1080})
  pg.set_content('<!doctype html><meta charset=utf-8><body>'+html); pg.wait_for_timeout(800)
  pg.evaluate('window.__fit1()')
  for i in range(N):
    pg.evaluate(f'window.__render({i/FPS*68/60})')
    pg.screenshot(path=f'{D}/{i:05d}.jpg',type='jpeg',quality=92)
  b.close()
subprocess.run(['ffmpeg','-y','-loglevel','error','-framerate',str(FPS),'-i',f'{D}/%05d.jpg','-c:v','libx264','-pix_fmt','yuv420p','-crf','17','-preset','slow','-movflags','+faststart',os.path.dirname(os.path.abspath(__file__))+'/prob_live_demo.mp4'],check=True)
print('ok')
