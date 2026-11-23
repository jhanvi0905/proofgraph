import sys
from pypdf import PdfReader, PdfWriter
src, out, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
r = PdfReader(src); w = PdfWriter()
for i in range(first-1, last): w.add_page(r.pages[i])
with open(out, "wb") as f: w.write(f)
