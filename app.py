# Todos direitos autorais reservados pelo QOTA.

import pytesseract
from flask import Flask, request, jsonify
from pdf2image import convert_from_bytes
import unicodedata
import re
import fitz  # PyMuPDF

# --- Configuração ---
pytesseract.pytesseract.tesseract_cmd = r'D:\TCC\tesseract.exe'
app = Flask(__name__)

# --- Funções Auxiliares ---
def normalize_text(text):
    if not text:
        return ""
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return ' '.join(text.lower().split())

# --- Rota Principal da API ---
@app.route('/processar-documento', methods=['POST'])
def process_document():
    if 'arquivo' not in request.files or not request.files['arquivo'].filename.lower().endswith('.pdf'):
        return jsonify({"detail": "Requisição inválida. Apenas arquivos PDF são aceitos."}), 400
    
    file = request.files['arquivo']
    address_from_form = request.form.get('endereco_formulario')
    cep_from_form = request.form.get('cep_formulario', '').strip()
    
    try:
        pdf_bytes = file.read()
        full_text = ""

        # --- NOVA ESTRATÉGIA DE EXTRAÇÃO ---
        # 1. Tenta extrair o texto diretamente com PyMuPDF (rápido e preciso)
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                full_text += page.get_text()

        # 2. OCR como Fallback: se a extração direta falhar (pouco texto), usa o OCR.
        if len(full_text.strip()) < 100: # Limite arbitrário para detectar PDFs de imagem
            print(">>> Extração direta falhou ou retornou pouco texto. Usando OCR como fallback...")
            images = convert_from_bytes(pdf_bytes)
            full_text = ""
            for img in images:
                # Usamos a configuração padrão do Tesseract, que é mais geral
                full_text += pytesseract.image_to_string(img, lang='por', config=r'--oem 3 --psm 3') + "\n"

        normalized_document_text = normalize_text(full_text)
        
        print("\n--- TEXTO EXTRAÍDO (NORMALIZADO) ---")
        print(normalized_document_text)
        print("------------------------------------\n")

        # --- LÓGICA DE VALIDAÇÃO HIERÁRQUICA (sem fuzzy, como solicitado) ---
        print("--- Iniciando Validação Hierárquica ---")

        # Tentativa 1: CEP
        cep_cleaned = re.sub(r'\D', '', cep_from_form)
        doc_text_cleaned_for_cep = re.sub(r'\D', '', normalized_document_text)
        
        print(f"Tentativa 1: Buscando CEP exato '{cep_cleaned}'...")
        if cep_cleaned and cep_cleaned in doc_text_cleaned_for_cep:
            print(">>> SUCESSO: CEP encontrado.")
            return jsonify({"mensagem": "Endereço validado com sucesso via CEP."}), 200
        else:
            print(">>> FALHA: CEP não encontrado.")

        # Tentativa 2: Logradouro
        logradouro = normalize_text(address_from_form).split(',')[0].strip()
        words_in_logradouro = logradouro.split()
        
        print(f"Tentativa 2: Buscando pelas palavras do logradouro '{logradouro}'...")
        regex_pattern = r'.*'.join(re.escape(word) for word in words_in_logradouro)
        
        if re.search(regex_pattern, normalized_document_text):
            print(">>> SUCESSO: Logradouro encontrado.")
            return jsonify({"mensagem": "Endereço validado com sucesso via Logradouro."}), 200
        else:
            print(">>> FALHA: Logradouro não encontrado.")

        print("--- FALHA EM TODAS AS TENTATIVAS ---")
        return jsonify({"detail": "Endereço não está presente no documento! Envie o arquivo correto."}), 400

    except Exception as e:
        print(f"Ocorreu um erro no serviço de OCR: {e}")
        return jsonify({"detail": "Não foi possível processar o arquivo PDF."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)