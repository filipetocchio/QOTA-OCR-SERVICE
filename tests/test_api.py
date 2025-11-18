# Todos direitos autorais reservados pelo QOTA.

"""
Testes de Integração (API Endpoint)

Descrição:
Esta suíte de testes valida o endpoint principal '/processar-documento'.

Princípios:
- Foco: Testa a camada de HTTP (rotas, validação de entrada, códigos de
  status) e a orquestração da lógica de negócios.
- Mocking (Simulação): A função 'extract_text_from_pdf' é completamente
  mockada. Isso nos permite testar a API sem depender de arquivos reais,
  OCR ou Tesseract, tornando os testes ultra-rápidos e 100% confiáveis.
"""

import io
import pytest

# 'mocker' vem do pytest-mock
# 'client' vem do nosso conftest.py
def test_processar_documento_sem_arquivo(client):
    """Testa a falha (400) se nenhum arquivo for enviado."""
    response = client.post('/processar-documento')
    json_data = response.get_json()
    
    assert response.status_code == 400
    assert "O campo 'arquivo' é obrigatório" in json_data.get("detail")

def test_processar_documento_arquivo_nao_pdf(client):
    """Testa a falha (400) se um arquivo que não é PDF for enviado."""
    data = {
        'arquivo': (io.BytesIO(b"conteudo"), 'documento.txt')
    }
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()

    assert response.status_code == 400
    assert "Apenas arquivos no formato PDF" in json_data.get("detail")

def test_processar_documento_falha_na_extracao(client, mocker):
    """Testa a falha (400) se o OCR não conseguir extrair texto."""
    # Mocka 'extract_text_from_pdf' para retornar None
    mocker.patch('app.extract_text_from_pdf', return_value=None)

    data = {'arquivo': (io.BytesIO(b"pdf-falso"), 'fatura.pdf')}
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()
    
    assert response.status_code == 400
    assert "Não foi possível extrair texto" in json_data.get("detail")

# --- Testes da Lógica 'extracao_conta' ---

def test_extracao_conta_sucesso(client, mocker):
    """Testa o caminho feliz (200) da extração de fatura."""
    # 1. Define o texto que o OCR "encontraria"
    texto_mockado = """
    fatura de energia eletrica
    vencimento: 15/10/2025
    total a pagar r$ 150,00
    """
    
    # 2. Mocka a extração
    mocker.patch('app.extract_text_from_pdf', return_value=texto_mockado)

    # 3. Prepara a requisição
    data = {
        'arquivo': (io.BytesIO(b"pdf-falso"), 'fatura.pdf'),
        'tipo_analise': 'extracao_conta'
    }
    
    # 4. Executa
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()

    # 5. Valida
    assert response.status_code == 200
    assert json_data["mensagem"] == "Dados da fatura extraídos com sucesso."
    assert json_data["dados"]["categoria"] == "Energia"
    assert json_data["dados"]["data_vencimento"] == "15/10/2025"
    assert json_data["dados"]["valor_total"] == "150.00"

def test_extracao_conta_dados_nao_encontrados(client, mocker):
    """Testa a falha (422) quando o texto não contém os dados essenciais."""
    # 1. Texto "ruim" (não contém valor ou vencimento)
    texto_mockado = "fatura de energia eletrica"
    
    # 2. Mocka a extração
    mocker.patch('app.extract_text_from_pdf', return_value=texto_mockado)

    # 3. Prepara a requisição
    data = {
        'arquivo': (io.BytesIO(b"pdf-falso"), 'fatura.pdf'),
        'tipo_analise': 'extracao_conta'
    }
    
    # 4. Executa
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()

    # 5. Valida
    assert response.status_code == 422
    assert "Dados essenciais (valor e vencimento) não foram encontrados" in json_data.get("detail")

# --- Testes da Lógica 'validacao_endereco' ---

def test_validacao_endereco_sucesso_cep(client, mocker):
    """Testa o caminho feliz (200) da validação de endereço por CEP."""
    # 1. Texto do documento
    texto_mockado = "meu endereco rua x, 123 cep 75000-000"
    mocker.patch('app.extract_text_from_pdf', return_value=texto_mockado)

    # 2. Dados do formulário
    data = {
        'arquivo': (io.BytesIO(b"pdf-falso"), 'comprovante.pdf'),
        'tipo_analise': 'validacao_endereco',
        'cep_formulario': '75000-000' # CEP correto
    }
    
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()

    assert response.status_code == 200
    assert "Endereço validado com sucesso via CEP" in json_data.get("mensagem")

def test_validacao_endereco_falha(client, mocker):
    """Testa a falha (400) quando o endereço não bate."""
    texto_mockado = "meu endereco rua x, 123 cep 75000-000"
    mocker.patch('app.extract_text_from_pdf', return_value=texto_mockado)

    data = {
        'arquivo': (io.BytesIO(b"pdf-falso"), 'comprovante.pdf'),
        'tipo_analise': 'validacao_endereco',
        'cep_formulario': '11111-111' # CEP errado
    }
    
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()

    assert response.status_code == 400
    assert "O endereço fornecido não corresponde" in json_data.get("detail")

def test_erro_interno_500(client, mocker):
    """Testa a captura de erro genérica (500)."""
    # Força a função 'extract_text_from_pdf' a levantar uma exceção
    mocker.patch('app.extract_text_from_pdf', side_effect=Exception("Erro de Teste"))

    data = {'arquivo': (io.BytesIO(b"pdf-falso"), 'fatura.pdf')}
    response = client.post('/processar-documento', content_type='multipart/form-data', data=data)
    json_data = response.get_json()
    
    assert response.status_code == 500
    assert "Ocorreu um erro interno" in json_data.get("detail")