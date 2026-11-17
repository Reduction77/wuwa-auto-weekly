import main
import sys
from PIL import Image
from rapidocr import RapidOCR
import numpy as np
from garden.weekly import classify_guide

ocr = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads':2})
for path in sys.argv[1:]:
    im = Image.open(path).convert('RGB')
    r = ocr(np.array(im))
    rows = [] if r.boxes is None else [(t,float(s),tuple(np.mean(b,axis=0))) for b,t,s in zip(r.boxes,r.txts,r.scores)]
    v = classify_guide(rows,*im.size)
    print({'page':v.page,'current':v.current,'target':v.target,'status':v.status},flush=True)
