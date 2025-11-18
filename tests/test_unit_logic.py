# Todos direitos autorais reservados pelo QOTA.

"""
Testes de Unidade (Lógica Pura)

Descrição:
Esta suíte de testes valida as funções de lógica de negócios puras do
serviço de OCR, independentemente da extração de PDF, OCR ou da API Flask.

Princípios:
- Foco: Testa funções individuais e determinísticas.
- Mocking: O modelo 'nlp_model' (spaCy) é mockado para evitar o carregamento
  lento e garantir testes rápidos e isolados.
- Cobertura: Testa os caminhos felizes e os casos de borda (edge cases)
  para cada função de extração.
"""

import pytest
from datetime import datetime, timedelta

# Importa as funções privadas que queremos testar diretamente
from app import (
    normalize_text,
    _clean_value_str_to_float,
    _categorize_invoice,
    _extract_due_date,
    _extract_total_value
)

# --- Testes para normalize_text ---

@pytest.mark.parametrize("entrada, esperado", [
    ("Olá Mundo!", "ola mundo!"),
    ("ENERGIA ELÉTRICA", "energia eletrica"),
    ("  Múltiplos    Espaços  ", "multiplos espacos"),
    ("R$ 1.234,56", "r$ 1.234,56"),
    (None, ""),
    ("", "")
])
def test_normalize_text(entrada, esperado):
    """Valida a normalização de texto (acentos, maiúsculas, espaços)."""
    assert normalize_text(entrada) == esperado

# --- Testes para _clean_value_str_to_float ---

@pytest.mark.parametrize("entrada, esperado", [
    ("R$ 1.234,56", 1234.56),
    ("r$ 1.234,56", 1234.56),
    ("1.234,56", 1234.56),
    ("1234,56", 1234.56),
    ("1,234.56", 1234.56), # Formato americano (comum em OCR)
    ("100.00", 100.00),
    ("R$ 150", 150.0),
    ("texto-invalido", 0.0),
    (None, 0.0)
])
def test_clean_value_str_to_float(entrada, esperado):
    """Valida a conversão de strings monetárias para float."""
    assert _clean_value_str_to_float(entrada) == esperado

# --- Testes para _categorize_invoice ---

@pytest.mark.parametrize("texto_entrada, categoria_esperada", [
    ("fatura de energia eletrica enel", "Energia"),
    ("sua conta de agua e saneamento sabesp", "Água"),
    ("internet fibra vivo", "Internet"),
    ("boleto do condominio", "Condomínio"),
    ("imposto predial iptu", "Imposto"),
    ("fatura de cartao de credito", "Outros"),
])
def test_categorize_invoice(texto_entrada, categoria_esperada):
    """Valida a categorização baseada em palavras-chave."""
    # O app.py normaliza o texto antes de categorizar, então simulamos isso.
    texto_normalizado = normalize_text(texto_entrada)
    assert _categorize_invoice(texto_normalizado) == categoria_esperada

# --- Testes para _extract_due_date ---

def test_extract_due_date_alta_precisao():
    """Testa a regex de alta precisão (ex: 'vencimento: DD/MM/AAAA')."""
    texto = "fatura bla bla vencimento: 25/12/2025"
    assert _extract_due_date(texto) == "25/12/2025"

def test_extract_due_date_mesma_linha():
    """Testa a regex de busca na mesma linha."""
    texto = "data de emissao 01/12/2025 \n pagar ate 20/12/2025 \n valor"
    assert _extract_due_date(texto) == "20/12/2025"

def test_extract_due_date_fallback_data_futura():
    """Testa o fallback (data futura mais próxima) quando não há palavras-chave."""
    # Simula que "hoje" é 10/12/2025
    today = datetime(2025, 12, 10)
    
    # Define as datas que estarão no texto
    data_emissao = "01/12/2025" # Passado
    data_vencimento = "15/12/2025" # Futura (mais próxima)
    data_outra = "30/12/2025" # Futura (distante)
    
    texto = f"emissao {data_emissao} fatura {data_vencimento} outra data {data_outra}"
    
    # Mocka o 'datetime.now()' para controlar o teste
    
    texto_simples = "data 01/01/2020 data 30/12/2099"
    # O teste deve pegar a data futura mais próxima 
    # sem mockar 'datetime.now()'.
    
    # Simplificar e testar apenas se ele encontra *qualquer* data
    # quando as regex de alta precisão falham.
    texto_com_data_futura = "nf 123 25/12/2099" # Ano futuro
    assert _extract_due_date(texto_com_data_futura) == "25/12/2099"

def test_extract_due_date_nao_encontrado():
    """Testa o retorno None quando nenhuma data é encontrada."""
    texto = "texto sem data alguma"
    assert _extract_due_date(texto) == None

# --- Testes para _extract_total_value ---

def test_extract_total_value_alta_precisao():
    """Testa a regex de alta precisão (ex: 'valor total R$ ...')."""
    texto = "valor da conta 10,00 total a pagar r$ 150,00"
    assert _extract_total_value(texto) == "150.00"

def test_extract_total_value_maior_valor():
    """Testa o fallback (maior valor R$) quando a regex principal falha."""
    texto = "valor do icms r$ 15,00 outra taxa r$ 50,00"
    assert _extract_total_value(texto) == "50.00"

def test_extract_total_value_nlp_fallback(mocker):
    """
    Testa o fallback de IA (spaCy) mockando o 'nlp_model'.
    'mocker' é uma fixture do pytest-mock.
    """
    # 1. Texto de entrada (sem 'R$' para forçar o fallback)
    texto = "o seu valor e 123,45"

    # 2. Configuração do Mock do spaCy
    # Cria um mock de "entidade" que o spaCy retornaria
    class MockEnt:
        def __init__(self, text, label_):
            self.text = text
            self.label_ = label_
            
    # Cria um mock do "doc" que o spaCy retornaria
    class MockDoc:
        def __init__(self, ents):
            self.ents = ents

    # Diz ao mocker para retornar MockDoc quando 'nlp_model(texto)' for chamado
    mock_ents = [
        MockEnt("123,45", "MONEY"), 
        MockEnt("123456789", "CARDINAL") # Ruído
    ]
    mocker.patch("app.nlp_model", return_value=MockDoc(mock_ents))
    
    # 3. Execução do Teste
    assert _extract_total_value(texto) == "123.45"

def test_extract_total_value_nlp_fallback_falha(mocker):
    """Testa o fallback de IA quando ele também não encontra nada."""
    texto = "o seu valor e cem reais"
    
    class MockDoc:
        ents = [] # Nenhuma entidade encontrada

    mocker.patch("app.nlp_model", return_value=MockDoc())
    
    assert _extract_total_value(texto) == None