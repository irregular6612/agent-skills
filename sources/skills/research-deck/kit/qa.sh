#!/bin/zsh
# Render a .pptx to PNG pages + contact sheets for visual QA.  qa.sh out/x.pptx
set -e
in=$1; dir=${in:r}-qa; rm -rf $dir; mkdir -p $dir
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf --outdir $dir $in >/dev/null 2>&1
pdftoppm -r 60 -png $dir/*.pdf $dir/p
python3 - $dir <<'PY'
import sys,glob
from PIL import Image
d=sys.argv[1]; ps=sorted(glob.glob(d+'/p-*.png'))
for k in range(0,len(ps),12):
    ims=[Image.open(p) for p in ps[k:k+12]]; w,h=ims[0].size
    sheet=Image.new('RGB',(w*3+20,h*4+30),'#888')
    for i,im in enumerate(ims): sheet.paste(im,((i%3)*(w+10),(i//3)*(h+10)))
    sheet.save(f'{d}/sheet{k//12+1}.png')
print(len(ps),'pages')
PY
