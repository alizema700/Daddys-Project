import base64,os
P='/tmp/claude-0/-home-claude-daddys-project/23319b1b-82f8-5df7-b06b-543874967567/scratchpad/package/files/'
css=''.join(f'@font-face{{font-family:"Instrument Sans";font-style:normal;font-weight:{w};font-display:block;src:url(data:font/woff2;base64,{base64.b64encode(open(P+f"instrument-sans-latin-{w}-normal.woff2","rb").read()).decode()}) format("woff2")}}\n' for w in (400,500,600,700))
d=os.path.dirname(os.path.abspath(__file__))
open(d+'/prob_live_demo.html','w').write(open(d+'/src.html').read().replace('/*FONTS*/',css).replace('/*PAPER*/',open(d+'/paper_p1.b64').read()))
