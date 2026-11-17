"""Read-only screenshot regression; prints states and counts, never account labels."""
import main
import sys
from PIL import Image
import numpy as np
from rapidocr import RapidOCR
from garden.cn_login import classify

ocr = RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                       'EngineConfig.onnxruntime.inter_op_num_threads': 2})
for path in sys.argv[1:]:
    image = Image.open(path).convert('RGB')
    result = ocr(np.array(image))
    rows = [] if result.boxes is None else [
        (text,float(score),((float(box[0][0])+float(box[2][0]))/2,
                           (float(box[0][1])+float(box[2][1]))/2))
        for box,text,score in zip(result.boxes,result.txts,result.scores)]
    view = classify(rows,*image.size)
    print({'state':view.state,'account_count':len(view.accounts),
           'selected_detected':bool(view.selected),'actions':list(view.targets)},flush=True)
