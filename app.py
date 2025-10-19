# Todos os direitos autorais reservados pelo QOTA.

"""
API de Processamento de Documentos - QOTA

Descrição:
Este módulo implementa uma API Flask projetada para a extração inteligente de dados de
arquivos PDF. A API possui um endpoint principal, '/processar-documento', que
orquestra duas funcionalidades distintas com base no parâmetro 'tipo_analise':

1.  Extração de Faturas ('extracao_conta'): Recebe um PDF de uma conta (água, energia, etc.),
    realiza o Reconhecimento Óptico de Caracteres (OCR) se necessário, e extrai
    informações cruciais como valor total, data de vencimento e categoria da despesa.
    Utiliza uma abordagem hierárquica, combinando expressões regulares de alta precisão
    com modelos de Processamento de Linguagem Natural (NLP) para robustez.

2.  Validação de Endereço ('validacao_endereco'): Compara um endereço e CEP fornecidos
    em um formulário com o conteúdo do documento PDF para verificar a correspondência,
    servindo como um mecanismo de comprovação de residência.

O sistema foi construído com uma arquitetura resiliente, que primeiramente tenta
extrair texto nativo do PDF e, como alternativa, aplica técnicas de pré-processamento
de imagem (OpenCV) antes do OCR (Tesseract) para maximizar a precisão.

Dependências principais:
- Flask: Para a criação do servidor web e da API.
- PyMuPDF (fitz): Para a extração de texto nativo de PDFs.
- pdf2image: Para converter páginas de PDF em imagens para o OCR.
- pytesseract: Wrapper Python para o motor Tesseract OCR.
- OpenCV (cv2): Para pré-processamento de imagens.
- spaCy: Para reconhecimento de entidades (NER) em texto.
- python-dotenv: Para gerenciamento de variáveis de ambiente.
"""

# --- Importações de Bibliotecas ---
import os
import re
import unicodedata
from datetime import datetime
import numpy as np
import cv2  # OpenCV
import fitz  # PyMuPDF
import pytesseract
import spacy
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pdf2image import convert_from_bytes

# --- Constantes e Configurações Globais ---
# Carrega variáveis de ambiente do arquivo .env. Essencial para configurar
# o ambiente sem expor dados sensíveis no código.
load_dotenv()

# Inicialização da aplicação Flask.
app = Flask(__name__)

# Constantes para tipos de análise, evitando o uso de strings "mágicas" no código.
ANALYSIS_TYPE_EXTRACTION = 'extracao_conta'
ANALYSIS_TYPE_VALIDATION = 'validacao_endereco'

# Limiar de caracteres para decidir se o OCR é necessário. PDFs com pouco texto
# extraído diretamente são provavelmente baseados em imagem.
OCR_TEXT_LENGTH_THRESHOLD = 150

# --- Configuração de Dependências Externas (Tesseract e spaCy) ---

def configure_tesseract():
    """
    Configura o caminho para o executável do Tesseract OCR.
    Valida a instalação e a acessibilidade do Tesseract antes de iniciar a API.
    """
    tesseract_path = os.getenv('TESSERACT_CMD')
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        print(f"INFO: Tesseract configurado via .env: {tesseract_path}")
    else:
        print("INFO: TESSERACT_CMD não definido ou inválido. Usando o PATH do sistema.")

    try:
        version = pytesseract.get_tesseract_version()
        print(f"INFO: Tesseract versão {version} detectado com sucesso.")
    except pytesseract.TesseractNotFoundError:
        # Interrompe a execução se o Tesseract não for encontrado, pois é uma dependência crítica.
        raise RuntimeError(
            "FATAL: Tesseract OCR não foi encontrado. "
            "Instale-o ou defina o caminho na variável TESSERACT_CMD no arquivo .env."
        )

def load_spacy_model():
    """
    Carrega o modelo de linguagem do spaCy para Processamento de Linguagem Natural.
    Retorna o modelo carregado ou None se não for encontrado.
    """
    try:
        model = spacy.load("pt_core_news_lg")
        print("INFO: Modelo 'pt_core_news_lg' do spaCy carregado com sucesso.")
        return model
    except OSError:
        print("AVISO: Modelo 'pt_core_news_lg' do spaCy não encontrado.")
        print("Execute: python -m spacy download pt_core_news_lg para instalá-lo.")
        return None

# Executa as configurações na inicialização do módulo.
configure_tesseract()
nlp_model = load_spacy_model()


# --- Funções de Pré-processamento e Extração de Texto ---

def normalize_text(text: str) -> str:
    """
    Padroniza o texto para análise: remove acentos, converte para minúsculas
    e normaliza espaços em branco. Isso torna as buscas por texto mais
    confiáveis e independentes de formatação.

    Args:
        text: A string de texto a ser normalizada.

    Returns:
        O texto normalizado.
    """
    if not text:
        return ""
    # Decompõe os caracteres (e.g., 'á' para 'a' + '´') e remove os acentos.
    text_no_accents = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    # Converte para minúsculas e remove espaços múltiplos.
    return ' '.join(text_no_accents.lower().split())

def preprocess_image_for_ocr(image):
    """
    Aplica filtros de pré-processamento a uma imagem para otimizar a precisão do OCR.

    Args:
        image: Um objeto de imagem (formato PIL).

    Returns:
        A imagem processada e pronta para o OCR (formato OpenCV).
    """
    # Converte a imagem do formato PIL para um array NumPy, que é o formato usado pelo OpenCV.
    img_cv = np.array(image)

    # A conversão para escala de cinza é um passo padrão que simplifica a imagem
    # sem perder as informações de contraste necessárias para reconhecer o texto.
    gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)

    # O thresholding adaptativo binariza a imagem (converte para preto e branco),
    # destacando o texto de forma eficaz mesmo sob condições de iluminação variáveis.
    processed_image = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return processed_image

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Implementa uma estratégia híbrida para extrair texto de um PDF.

    1.  Tenta extrair texto diretamente, o que é rápido e preciso para PDFs textuais.
    2.  Se o resultado for insatisfatório (sugerindo um PDF de imagem),
        converte as páginas para imagens e aplica OCR.

    Args:
        pdf_bytes: O conteúdo do arquivo PDF em bytes.

    Returns:
        O texto completo extraído e normalizado do documento.
    """
    full_text = ""
    # Estratégia 1: Extração de texto nativo com PyMuPDF.
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                full_text += page.get_text()
    except Exception as e:
        print(f"AVISO: Falha na extração de texto direto com PyMuPDF: {e}")
        full_text = ""

    # Estratégia 2: Fallback para OCR se a extração direta falhar ou retornar pouco texto.
    if len(full_text.strip()) < OCR_TEXT_LENGTH_THRESHOLD:
        print("INFO: Baixo volume de texto extraído. Iniciando processo de OCR.")
        try:
            images = convert_from_bytes(pdf_bytes)
            ocr_texts = []
            for img in images:
                processed_img = preprocess_image_for_ocr(img)
                # Configurações do Tesseract: 'por' para português, OEM 3 e PSM 6 são bons
                # padrões para layouts de documentos variados.
                ocr_texts.append(
                    pytesseract.image_to_string(processed_img, lang='por', config=r'--oem 3 --psm 6')
                )
            full_text = "\n".join(ocr_texts)
        except Exception as e:
            print(f"ERRO: Falha durante o processo de OCR: {e}")
            return "" # Retorna vazio se ambas as estratégias falharem.

    return normalize_text(full_text)


# --- Funções de Lógica de Negócios (Extração de Dados) ---

def _extract_due_date(text: str) -> str | None:
    """
    Localiza a data de vencimento no texto usando uma busca hierárquica.

    1.  Busca por padrões de alta precisão (e.g., "vencimento: DD/MM/AAAA").
    2.  Busca por datas na mesma linha que palavras-chave como "vencimento".
    3.  Como fallback, encontra todas as datas no texto e retorna a data futura mais próxima.
    """
    # Tentativa 1: Regex de alta precisão.
    match = re.search(r'(?:vencimento|vence\s*em|pagar\s+ate)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})', text)
    if match:
        return match.group(1)

    # Tentativa 2: Busca na mesma linha.
    for line in text.split('\n'):
        if any(kw in line for kw in ['vencimento', 'vence em', 'pagar ate']):
            line_match = re.search(r'(\d{2}/\d{2}/\d{2,4})', line)
            if line_match:
                return line_match.group(1)

    # Tentativa 3: Fallback inteligente para a data futura mais próxima.
    all_dates_str = re.findall(r'(\d{2}/\d{2}/\d{2,4})', text)
    future_dates = []
    today = datetime.now()
    for date_str in all_dates_str:
        try:
            day, month, year_str = date_str.split('/')
            year = int(f"20{year_str}" if len(year_str) == 2 else year_str)
            date_obj = datetime(year, int(month), int(day))
            # Considera apenas datas futuras para evitar capturar datas de emissão.
            if date_obj >= today.replace(hour=0, minute=0, second=0, microsecond=0):
                future_dates.append((date_obj, date_str))
        except ValueError:
            continue
    
    if future_dates:
        # Retorna a data futura mais próxima do dia de hoje.
        closest_date = min(future_dates, key=lambda x: x[0])
        return closest_date[1]
        
    return None

def _clean_value_str_to_float(value_str: str) -> float:
    """Converte uma string monetária (e.g., "R$ 1.234,56") para um float."""
    try:
        # Limpeza robusta para diferentes formatos monetários.
        cleaned = value_str.lower().replace('r$', '').strip()
        cleaned = cleaned.replace('.', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0

def _extract_total_value(text: str) -> str | None:
    """
    Localiza o valor total a pagar no texto usando uma busca hierárquica.

    1.  Busca por padrões de alta precisão (e.g., "valor total R$ ...").
    2.  Encontra todos os valores monetários ("R$ ...") e assume o maior como total.
    3.  Utiliza o modelo de NLP (spaCy) para identificar entidades "MONEY".
    """
    # Prioridade 1: Regex de alta confiança.
    match = re.search(r'(?:total\s+a\s+pagar|valor\s+total|total\s+da\s+conta)\s*r?\$\s*([\d.,]+)', text)
    if match:
        return str(_clean_value_str_to_float(match.group(1)))

    # Prioridade 2: Pega o maior valor monetário encontrado.
    matches = re.findall(r'r\$\s*([\d.,]{2,})', text)
    if matches:
        possible_values = [_clean_value_str_to_float(v) for v in matches]
        if possible_values:
            return f"{max(possible_values):.2f}"

    # Prioridade 3: Usa IA (spaCy) como último recurso.
    if nlp_model:
        doc = nlp_model(text)
        money_values = [
            _clean_value_str_to_float(ent.text) for ent in doc.ents
            if ent.label_ == "MONEY" and any(c.isdigit() for c in ent.text)
        ]
        if money_values:
            # Filtra valores muito grandes que podem ser códigos de barras ou outros números.
            valid_values = [v for v in money_values if 0 < v < 1_000_000]
            if valid_values:
                 return f"{max(valid_values):.2f}"
    
    return None

def _categorize_invoice(text: str) -> str:
    """
    Classifica o tipo de conta (categoria) com base em palavras-chave.
    A estrutura de dicionário facilita a adição de novas categorias e palavras-chave.
    """
    CATEGORIES = {
        "Internet": ["internet", "telecom", "fibra", "banda larga", "vivo", "claro", "tim", "oi", "algar", "brisanet"],
        "Energia": ["energia", "eletrica", "eletrobras", "neoenergia", "enel", "cpfl", "equatorial", "cemig", "light"],
        "Água": ["agua", "saneamento", "sabesp", "copasa", "sanepar", "casan", "aegea", "igua", "corsan", "embasa"],
        "Condomínio": ["condominio"],
        "Imposto": ["iptu", "imposto predial", "tributo"]
    }
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category
    
    # Retorna uma categoria padrão se nenhuma correspondência for encontrada.
    return "Outros"

def extract_financial_data(text: str) -> dict:
    """
    Orquestra a extração de todos os dados financeiros de uma fatura.

    Args:
        text: O texto completo extraído do documento.

    Returns:
        Um dicionário contendo o valor total, data de vencimento e categoria.
    """
    total_value = _extract_total_value(text)
    due_date = _extract_due_date(text)
    category = _categorize_invoice(text)

    return {
        "valor_total": total_value,
        "data_vencimento": due_date,
        "categoria": category
    }

# --- Rotas da API (Endpoints) ---

@app.route('/processar-documento', methods=['POST'])
def process_document_route():
    """
    Endpoint principal da API. Recebe um arquivo PDF e o tipo de análise,
    valida a entrada, orquestra o processamento e retorna o resultado em JSON.
    """
    # 1. Validação da Requisição
    if 'arquivo' not in request.files:
        return jsonify({"detail": "O campo 'arquivo' é obrigatório."}), 400

    file = request.files['arquivo']
    if not file or not file.filename.lower().endswith('.pdf'):
        return jsonify({"detail": "Apenas arquivos no formato PDF são permitidos."}), 400

    analysis_type = request.form.get('tipo_analise', ANALYSIS_TYPE_VALIDATION)
    
    # 2. Processamento do Arquivo
    try:
        pdf_bytes = file.read()
        extracted_text = extract_text_from_pdf(pdf_bytes)
        
        if not extracted_text:
            return jsonify({"detail": "Não foi possível extrair texto do documento. Verifique a qualidade do arquivo."}), 400

        # 3. Lógica de Negócio com base no Tipo de Análise
        if analysis_type == ANALYSIS_TYPE_EXTRACTION:
            financial_data = extract_financial_data(extracted_text)
            
            # Valida se os dados essenciais foram extraídos com sucesso.
            if not financial_data.get("valor_total") or not financial_data.get("data_vencimento"):
                return jsonify({"detail": "Dados essenciais (valor e vencimento) não foram encontrados."}), 422 # Unprocessable Entity

            return jsonify({
                "mensagem": "Dados da fatura extraídos com sucesso.",
                "dados": financial_data
            }), 200

        else: # O padrão é a validação de endereço
            address_from_form = request.form.get('endereco_formulario', '').strip()
            cep_from_form = request.form.get('cep_formulario', '').strip()

            if not address_from_form and not cep_from_form:
                 return jsonify({"detail": "Forneça o endereço ou CEP do formulário para validação."}), 400

            # Validação por CEP: é mais precisa e rápida.
            cep_cleaned = re.sub(r'\D', '', cep_from_form)
            if cep_cleaned and cep_cleaned in re.sub(r'\D', '', extracted_text):
                return jsonify({"mensagem": "Endereço validado com sucesso via CEP."}), 200

            # Validação por Logradouro: fallback se o CEP falhar.
            logradouro = normalize_text(address_from_form).split(',')[0].strip()
            if logradouro and re.search(r'\b' + r'\W*'.join(map(re.escape, logradouro.split())) + r'\b', extracted_text):
                return jsonify({"mensagem": "Endereço validado com sucesso via Logradouro."}), 200

            return jsonify({"detail": "O endereço fornecido não corresponde ao do documento."}), 400

    except Exception as e:
        # Captura de erro genérica para evitar o vazamento de detalhes internos.
        print(f"ERRO INESPERADO: {e}")
        return jsonify({"detail": "Ocorreu um erro interno ao processar o documento."}), 500


# --- Ponto de Entrada da Aplicação ---
if __name__ == '__main__':
    # A execução via 'app.run()' é ideal para desenvolvimento e depuração.
    # Em um ambiente de produção, utilize um servidor WSGI como Gunicorn ou uWSGI
    # para garantir performance, segurança e escalabilidade.
    # Exemplo com Gunicorn: gunicorn --bind 0.0.0.0:8000 your_module_name:app
    app.run(host='0.0.0.0', port=8000, debug=True)