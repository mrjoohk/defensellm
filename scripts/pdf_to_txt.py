#!/home/rtv-24n10/anaconda3/envs/defensellm/bin/python
# scripts/pdf_to_txt.py
import sys
import os

def pdf_to_txt(pdf_path, txt_path):
    print(f"Extracting text from: {pdf_path}")
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text_content = []
        for page in doc:
            text_content.append(page.get_text())
        doc.close()

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(text_content))
            
        print(f"Written: {txt_path} ({len(text_content)} pages)")
        return True
    except ImportError:
        print("PyMuPDF (fitz) is not installed. Trying pypdf...")
        try:
            import pypdf
            with open(pdf_path, 'rb') as fp:
                reader = pypdf.PdfReader(fp)
                text_content = []
                for page in reader.pages:
                    text_content.append(page.extract_text() or "")
                    
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(text_content))
            print(f"Written: {txt_path} ({len(reader.pages)} pages) via pypdf")
            return True
            
        except ImportError:
            print("pypdf is not installed. Cannot parse PDF.")
            return False
    except Exception as e:
        print(f"Failed to extract text from {pdf_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_to_txt.py <pdf_path>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)
        
    txt_path = pdf_path.rsplit('.', 1)[0] + '.txt'
    pdf_to_txt(pdf_path, txt_path)
