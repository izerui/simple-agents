import pdfplumber

with pdfplumber.open("../files/20210701012009-王怡入-拉格朗日中值定理在考研数学中的应用.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text(layout=True)
        print(text)