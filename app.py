# Todos direitos autorais reservados pelo QOTA.

import os
from dotenv import load_dotenv
import pytesseract
from flask import Flask, request, jsonify
from pdf2image import convert_from_bytes
import unicodedata
import re
import fitz  # PyMuPDF
import cv2   # OpenCV
import numpy as np
import spacy
from datetime import datetime

# --- CONFIGURAÇÃO DA APLICAÇÃO ---

# Carrega as variáveis de ambiente do arquivo .env para a aplicação.
load_dotenv()

# Inicializa a aplicação Flask.
app = Flask(__name__)

# --- CONFIGURAÇÃO DE DEPENDÊNCIAS EXTERNAS (TESSERACT E SPACY) ---

# Tenta configurar o caminho do Tesseract de forma flexível e robusta.
tesseract_path = os.getenv('TESSERACT_CMD')

# Se um caminho foi fornecido no .env, o script o valida e o utiliza.
if tesseract_path and os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    print(f"INFO: Tesseract configurado a partir do caminho em .env: {tesseract_path}")
else:
    # Se nenhum caminho foi especificado, o pytesseract tentará encontrar o Tesseract no PATH do sistema.
    print("INFO: TESSERACT_CMD não definido ou caminho inválido. Pytesseract tentará encontrar Tesseract no PATH do sistema.")

# Validação final para garantir que o Tesseract está acessível antes de iniciar.
try:
    tesseract_version = pytesseract.get_tesseract_version()
    print(f"INFO: Tesseract versão {tesseract_version} detectado e funcionando.")
except pytesseract.TesseractNotFoundError:
    # Se o Tesseract não for encontrado por nenhum método, a aplicação é interrompida com uma mensagem de erro clara.
    raise RuntimeError(
        "Tesseract não foi encontrado. Certifique-se de que ele está instalado e no PATH do seu sistema, "
        "ou especifique o caminho para o executável na variável TESSERACT_CMD no arquivo .env."
    )

# Carrega o modelo de linguagem do spaCy.
try:
    nlp = spacy.load("pt_core_news_lg")
except OSError:
    print("Modelo 'pt_core_news_lg' do spaCy não encontrado.")
    print("Para instalar, execute: python -m spacy download pt_core_news_lg")
    nlp = None

# --- FUNÇÕES DE PRÉ-PROCESSAMENTO E EXTRAÇÃO DE TEXTO ---

def normalize_text(text):
    """
    Normaliza uma string de texto, removendo acentos, convertendo para
    minúsculas e padronizando os espaços em branco para facilitar as buscas.
    """
    if not text:
        return ""
    # Remove acentos e caracteres diacríticos.
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    # Converte para minúsculas e remove espaços extras.
    return ' '.join(text.lower().split())

def preprocess_image_for_ocr(image):
    """
    Utiliza o OpenCV para aplicar filtros de pré-processamento em uma imagem,
    melhorando a precisão da extração de texto (OCR) pelo Tesseract.
    """
    img_cv = np.array(image)
    # Converte a imagem para escala de cinza.
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
    # Aplica um threshold adaptativo para binarizar a imagem, destacando o texto.
    processed_image = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return processed_image

def extract_text_from_pdf(pdf_bytes):
    """
    Extrai texto de um arquivo PDF utilizando uma estratégia híbrida:
    1. Tenta a extração direta de texto (para PDFs baseados em texto).
    2. Se o texto extraído for insuficiente, recorre ao OCR em cada página do PDF.
    """
    full_text = ""
    # Tentativa 1: Extração de texto direto com PyMuPDF.
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                full_text += page.get_text()
    except Exception:
        full_text = ""

    # Tentativa 2: Fallback para OCR se o texto for muito curto (sugere um PDF baseado em imagem).
    if len(full_text.strip()) < 150:
        images = convert_from_bytes(pdf_bytes)
        full_text = ""
        for img in images:
            processed_img = preprocess_image_for_ocr(img)
            # Utiliza o Tesseract para extrair texto da imagem processada.
            full_text += pytesseract.image_to_string(processed_img, lang='por', config=r'--oem 3 --psm 6') + "\n"
            
    return normalize_text(full_text)

# --- FUNÇÃO PRINCIPAL DE EXTRAÇÃO DE DADOS FINANCEIROS ---

def extract_financial_data(text):
    """
    Extrai dados financeiros de um texto usando uma estratégia hierárquica 
    para data de vencimento e valor total, garantindo maior precisão.
    """
    data = {
        "valor_total": None, 
        "data_vencimento": None,
        "categoria": "Outros"  # Categoria padrão caso nenhuma seja identificada.
    }
    
    # --- Função Auxiliar para Limpeza de Valores Monetários ---
    def clean_value_str_to_float(value_str):
        try:
            # Remove símbolos monetários, espaços, pontos de milhar e substitui a vírgula decimal.
            cleaned = value_str.lower().replace('r$', '').strip().replace('.', '').replace(',', '.')
            return float(cleaned)
        except (ValueError, AttributeError):
            return 0.0

    # --- 1. Extração Hierárquica da Data de Vencimento ---
    
    # Tentativa 1: Busca de alta precisão (palavra-chave + data DD/MM/AAAA adjacente).
    vencimento_match = re.search(r'(?:vencimento|vence\s*em|pagar\s+ate)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})', text)
    if vencimento_match:
        data["data_vencimento"] = vencimento_match.group(1)

    # Tentativa 2: Busca na mesma linha da palavra-chave.
    if not data["data_vencimento"]:
        for line in text.split('\n'):
            if any(kw in line for kw in ['vencimento', 'vence em', 'pagar ate']):
                match_in_line = re.search(r'(\d{2}/\d{2}/\d{2,4})', line)
                if match_in_line:
                    data["data_vencimento"] = match_in_line.group(1)
                    break
    
    # Tentativa 3: Fallback inteligente (pega a data cronologicamente mais próxima no futuro).
    if not data["data_vencimento"]:
        all_dates_str = re.findall(r'(\d{2}/\d{2}/\d{2,4})', text)
        future_dates = []
        today = datetime.now()
        for date_str in all_dates_str:
            try:
                day, month, year_str = date_str.split('/')
                year = f"20{year_str}" if len(year_str) == 2 else year_str
                date_obj = datetime(int(year), int(month), int(day))
                if date_obj >= today.replace(hour=0, minute=0, second=0, microsecond=0):
                    future_dates.append((date_obj, date_str))
            except ValueError:
                continue
        if future_dates:
            closest_future_date = min(future_dates, key=lambda x: x[0])
            data["data_vencimento"] = closest_future_date[1]

    # --- 2. Extração Hierárquica do Valor Total ---
    
    # Prioridade 1: Regex de alta confiança com palavras-chave diretas.
    p1_match = re.search(r'(?:total\s+a\s+pagar|valor\s+total|total\s+da\s+conta)\s*r?\$\s*([\d.,]+)', text)
    if p1_match:
        data["valor_total"] = p1_match.group(1)

    # Prioridade 2: Busca por todos os valores precedidos por "R$" e pega o maior.
    if not data["valor_total"]:
        p2_matches = re.findall(r'r\$\s*([\d.,]{2,})', text)
        if p2_matches:
            possible_values = [clean_value_str_to_float(v) for v in p2_matches]
            if possible_values:
                data["valor_total"] = f"{max(possible_values):.2f}"

    # Prioridade 3: Usa IA (spaCy) como último recurso.
    if not data["valor_total"] and nlp:
        doc = nlp(text)
        money_values = []
        for ent in doc.ents:
            if ent.label_ == "MONEY" and any(c.isdigit() for c in ent.text):
                val = clean_value_str_to_float(ent.text)
                if 0 < val < 1000000: # Filtro para evitar códigos de barras
                    money_values.append(val)
        if money_values:
            data["valor_total"] = f"{max(money_values):.2f}"
    
    # Garante que o formato final seja com ponto para o backend Node.
    if data["valor_total"] and isinstance(data["valor_total"], str):
        data["valor_total"] = data["valor_total"].replace(',', '.')

    # --- 3. Classificação de Categoria por Palavras-chave ---
    # Estrutura de dados para facilitar a manutenção e expansão das categorias.
    CATEGORIES = {
        "Internet": ["internet", "telecom", "fibra", "banda larga", "vivo", "claro", "tim", "oi", "algar", "brisanet"],
        "Energia": ["energia", "eletrica", "eletrobras", "neoenergia", "enel", "cpfl", "equatorial", "cemig", "light"],
        "Água": ["agua", "saneamento", "sabesp", "copasa", "sanepar", "casan", "aegea", "igua", "corsan", "embasa"],
        "Condomínio": ["condominio"],
        "Imposto": ["iptu", "imposto predial", "tributo"]
    }
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            data["categoria"] = category
            break # Atribui a primeira categoria encontrada e para a busca.

    return data

# --- ROTA PRINCIPAL DA API ---
@app.route('/processar-documento', methods=['POST'])
def process_document():
    """
    Endpoint principal que recebe um arquivo PDF e o tipo de análise,
    orquestrando o processo de extração e retornando os dados.
    """
    if 'arquivo' not in request.files:
        return jsonify({"detail": "Campo 'arquivo' não encontrado na requisição."}), 400
    
    file = request.files['arquivo']
    if not file or not file.filename.lower().endswith('.pdf'):
        return jsonify({"detail": "Apenas arquivos no formato PDF são aceitos."}), 400
    
    pdf_bytes = file.read()
    extracted_text = extract_text_from_pdf(pdf_bytes)
    
    analysis_type = request.form.get('tipo_analise', 'validacao_endereco')

    # --- Lógica para Extração de Fatura ---
    if analysis_type == 'extracao_conta':
        financial_data = extract_financial_data(extracted_text)
        # Valida se os campos essenciais foram extraídos.
        if not financial_data.get("valor_total") or not financial_data.get("data_vencimento"):
            return jsonify({"detail": "Não foi possível extrair os dados essenciais (valor e vencimento). Verifique a qualidade do documento."}), 400
        
        return jsonify({
            "mensagem": "Dados extraídos com sucesso.",
            "dados": financial_data
        }), 200

    # --- Lógica para Validação de Endereço (Mantida como estava) ---
    else:
        address_from_form = request.form.get('endereco_formulario')
        cep_from_form = request.form.get('cep_formulario', '').strip()
        
        # Validação por CEP
        cep_cleaned = re.sub(r'\D', '', cep_from_form)
        doc_text_cleaned_for_cep = re.sub(r'\D', '', extracted_text)
        if cep_cleaned and cep_cleaned in doc_text_cleaned_for_cep:
            return jsonify({"mensagem": "Endereço validado com sucesso via CEP."}), 200
        
        # Validação por Logradouro
        logradouro = normalize_text(address_from_form).split(',')[0].strip()
        words_in_logradouro = logradouro.split()
        regex_pattern = r'\b' + r'\W*'.join(re.escape(word) for word in words_in_logradouro) + r'\b'
        if re.search(regex_pattern, extracted_text):
            return jsonify({"mensagem": "Endereço validado com sucesso via Logradouro."}), 200

        return jsonify({"detail": "O endereço fornecido não corresponde ao do documento."}), 400

# --- PONTO DE ENTRADA DA APLICAÇÃO ---
if __name__ == '__main__':
    # Executa a aplicação em modo de depuração para desenvolvimento.
    # Para produção, um servidor WSGI como Gunicorn ou uWSGI deve ser utilizado.
    app.run(host='0.0.0.0', port=8000, debug=True)
