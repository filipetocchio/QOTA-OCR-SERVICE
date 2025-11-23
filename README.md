# Qota OCR Service

## Descrição

API de microsserviço em Flask para extração inteligente de dados e validação de documentos PDF. Utiliza uma arquitetura híbrida de extração de texto nativo (PyMuPDF), Reconhecimento Óptico de Caracteres (Tesseract) e Processamento de Linguagem Natural (spaCy) para garantir máxima precisão e flexibilidade no tratamento de faturas e comprovantes.

Este documento fornece uma visão técnica completa da arquitetura, fluxo de dados, decisões de design, e guias de instalação e uso da API.

---

##  Índice

1. Visão Geral e Vantagens Estratégicas  
   - Problema Solucionado  
   - Decisões de Design (Vantagens)  
   - Stack Tecnológico e Racional  

2. Arquitetura e Fluxo de Processamento  
   - Fluxo 1: Extração Híbrida de Texto  
   - Fluxo 2: Lógica de Negócios Hierárquica  

3. Qualidade, Testes e CI/CD  
   - Filosofia de Testes  
   - Tipos de Teste (Unidade e Integração)  
   - Pipeline de CI (GitHub Actions)  
   - Como Executar os Testes  

4. Guia de Instalação  
   - Pré-requisitos de Sistema  
   - Configuração do Ambiente Python  
   - Instalação do Modelo spaCy  

5. Execução e Configuração  
   - Arquivo .env  
   - Modo Desenvolvimento  
   - Modo Produção  

6. Referência da API  
   - POST /processar-documento  
   - Exemplos completos  

7. Resumo dos Códigos de Erro  

8. Limitações e Próximos Passos  

---

#  1. Visão Geral e Vantagens Estratégicas

## Problema Solucionado

O microsserviço Qota OCR foi desenvolvido para resolver dois desafios centrais na plataforma QOTA:

- **Extração de Faturas:** Automatizar a entrada de dados de contas (água, energia, internet), que chegam em PDFs variados (textuais ou imagem). O sistema extrai valor total, vencimento e categoria.
- **Validação de Endereço:** Verificar automaticamente a autenticidade de um comprovante de residência comparando informações do PDF com as do formulário.

---

## Decisões de Design (Vantagens Estratégicas)

A arquitetura foi escolhida deliberadamente em vez de soluções SaaS “prontas para uso” como AWS Textract ou Google Vision AI. Motivos:

### Custo Zero (Open Source)

Todo o stack (Python, Flask, Tesseract, OpenCV, spaCy) é gratuito e open-source, permitindo escalabilidade sem custos por página.

### Controle Total e Flexibilidade

SaaS são caixas-pretas. Com nosso serviço:

-    Ajustamos pré-processamento (OpenCV) para PDFs ruidosos  
-    Refinamos heurísticas (Regex) para novos formatos  
-    Substituímos ou re-treinamos modelos spaCy  

### Privacidade e Não-Dependência

Nenhum documento é enviado a terceiros. O sistema roda em qualquer ambiente sem vendor lock-in.

---

## Stack Tecnológico e Racional

| Categoria | Tecnologia | Racional |
|----------|------------|----------|
| Framework Web | Flask | Leve, rápido e ideal para microsserviços REST |
| PDF (Texto Nativo) | PyMuPDF (fitz) | Extração vetorial extremamente precisa e veloz |
| PDF (Fallback) | pdf2image | Wrapper robusto do Poppler |
| OCR | Tesseract | Melhor OCR open source (LSTM) |
| Pré-processamento | OpenCV | Aumenta drasticamente a precisão do OCR |
| NLP (IA) | spaCy pt_core_news_lg | Reconhecimento de entidades (fallback final) |
| Testes | Pytest | Padrão da indústria, suporte total a mocks |
| Configuração | python-dotenv | Carregar variáveis de ambiente com segurança |

---

#  2. Arquitetura e Fluxo de Processamento

O serviço opera com dois fluxos principais: **extração de texto** e **lógica de negócios**.

---

## Fluxo 1: Extração Híbrida de Texto (`extract_text_from_pdf`)

### Tentativa de Extração Nativa (PyMuPDF)

- Abre o PDF via `fitz.open()`.
- Extração vetorial é instantânea e 100% precisa.
- Usado para faturas digitais (2ª via online, e-mails, etc.).

### Gatilho de Fallback

Se o texto extraído for **<150 caracteres** (valor de `OCR_TEXT_LENGTH_THRESHOLD`), assume-se que o PDF é baseado em imagem.

### Fluxo de OCR (Tesseract + OpenCV)

1. Conversão para imagens (Poppler → PIL)  
2. Pré-processamento (OpenCV):  
       -    `cv2.cvtColor(..., GRAY)`  
       -    `cv2.adaptiveThreshold(...)`  
3. Execução do Tesseract com:  
       -    `lang='por'`  
       -    `--oem 3 --psm 6`  
4. Normalização do texto:  
       -    minúsculas  
       -    remover acentos  

---

## Fluxo 2: Lógica de Negócios Hierárquica

Aplica regras de extração com prioridades estritas.

---

## A. Extração de Fatura (`extracao_conta`)

### Extração de Valor Total (`_extract_total_value`)

- **Prioridade 1 – Regex de Alta Precisão**  
       -    `(total\s+a\s+pagar|valor\s+total|total\s+da\s+conta)\s*r?\$\s*([\d.,]+)`
- **Prioridade 2 – Regex Fallback**  
       - encontra todos os valores `r\$\s*([\d.,]{2,})`  
       - seleciona o **maior** valor encontrado  
- **Prioridade 3 – IA (spaCy)**  
       - modelo identifica entidades MONEY no texto  

---

### Extração da Data de Vencimento (`_extract_due_date`)

- **Prioridade 1 – Regex de Alta Precisão**  
       - `(vencimento|vence\s*em|pagar\s+ate)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})`
- **Prioridade 2 – Fallback Inteligente**  
       - coleta TODAS as datas  
       - filtra datas passadas  
       - seleciona a **data futura mais próxima**

---

### Categorização da Fatura (`_categorize_invoice`)

- **Internet:** internet, telecom, fibra, vivo, claro, tim, oi, algar, brisanet  
- **Energia:** energia, eletrica, eletrobras, neoenergia, enel, cpfl, equatorial, cemig, light  
- **Água:** agua, saneamento, sabesp, copasa, sanepar, casan, aegea, igua, corsan, embasa  
- **Outros:** condominio, iptu, imposto predial  

---

## B. Validação de Endereço (`validacao_endereco`)

- **Prioridade 1 — CEP:**  
       - remove formatação  
       - compara CEP do PDF com o do formulário  
- **Prioridade 2 — Logradouro:**  
       - busca textual normalizada do nome da rua  

---

#  3. Qualidade, Testes e CI/CD

Uma suíte robusta garante estabilidade da lógica complexa de extração.

---

## Filosofia de Testes

- Não testamos se o Tesseract funciona.  
- Testamos se as **funções de extração** funcionam com textos simulados.  
- Isso é alcançado com mocks (`pytest-mock`).

---

## Tipos de Teste

### Testes de Unidade (`test_unit_logic.py`)

Foco nas funções puras:

- normalize_text  
- `_clean_value_str_to_float`  
- `_categorize_invoice`  
- Fallback via spaCy mockado  

### Testes de Integração (`test_api.py`)

- Testam o endpoint `/processar-documento`  
- Validação do corpo da requisição  
- Respostas JSON  
- Códigos de status  
- `extract_text_from_pdf` é **mockado**  

---

## Pipeline de CI (GitHub Actions)

Pipeline em `.github/workflows/ci.yml`:

1. Configura ambiente (Ubuntu + Python 3.10)  
2. Instala dependências do sistema:  
       - tesseract-ocr  
       - poppler-utils  
3. Instala Python deps (requirements.txt)  
4. Baixa modelo spaCy  
5. Executa flake8  
6. Executa pytest (interrompe em caso de falha)  

---

## Como Executar os Testes
```bash
    pip install pytest pytest-flask pytest-mock

    pytest

```
---

# 4. Guia de Instalação

## A. Pré-requisitos de Sistema

### 1. Tesseract-OCR

**Windows:**

- Baixar: https://github.com/UB-Mannheim/tesseract/wiki  
- Selecionar idioma "Portuguese"  
- Adicionar ao PATH: `C:\Program Files\Tesseract-OCR`

**Linux:**
```bash
    sudo apt-get install tesseract-ocr tesseract-ocr-por
```
---

### 2. Poppler

**Windows:**

- Baixar release: https://github.com/oschwartz10612/poppler-windows/releases  
- Extrair em: `C:\Program Files\poppler`  
- Adicionar ao PATH: `C:\Program Files\poppler\bin`

**Linux:**
```bash
    sudo apt-get install poppler-utils
```
---

### 3. Visual Studio Build Tools (Windows)

Necessário para compilar PyMuPDF.

- Baixar Build Tools  
- Selecionar workload "Desenvolvimento para desktop com C++"  
- Reiniciar máquina  

---

## B. Configuração do Ambiente Python
```bash
    git clone https://github.com/filipetocchio/Qota-OCR-Service.git
    cd Qota-OCR-Service

    python -m venv venv
```
**Ativar:**

- Windows:  
```bash
        .\venv\Scripts\activate
```
- Linux/macOS: 
```bash 
        source venv/bin/activate
```
```bash 
    python -m pip install --upgrade pip
    
    pip install -r requirements.txt
```
---

### Importante: Compatibilidade do PyMuPDF e Versão do Python

O PyMuPDF *não oferece suporte ao Python 3.13*.  
Se o ambiente virtual for criado usando essa versão, o pip tentará *compilar o PyMuPDF manualmente*, o que resulta em erros de "metadata" ou mensagens como:

Exception: Unable to find Visual Studio
metadata-generation-failed
PyMuPDF build error 

---

### ✅ Como resolver

Para instalar corretamente o PyMuPDF, é *obrigatório usar uma versão do Python suportada*, como:

- *Python 3.10*
- *Python 3.11*
- *Python 3.12* (recomendado)

---

### 🛠️ Passo a passo

#### 1. Instale uma versão suportada do Python (3.10–3.12)
Baixe em:  
https://www.python.org/downloads/

---

#### 2. Apague o ambiente virtual atual (caso tenha sido criado com Python 3.13)

```bash
rmdir venv /s /q
```

#### 3. Crie um novo ambiente virtual usando uma versão compatível do Python (ex.: 3.12)

```bash
py -3.12 -m venv venv
```

####  4. Ative o ambiente virtual

```bash
.\venv\Scripts\activate
```

#### 5. Reinstale as dependências

```bash
pip install -r requirements.txt
```
---

## C. Instalação do Modelo spaCy
```bash
    python -m spacy download pt_core_news_lg
```
---

# 5. Execução e Configuração

## Arquivo `.env` (Opcional)

    # TESSERACT_CMD="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

---

## Modo Desenvolvimento
```bash
    python app.py
```
Servidor: http://127.0.0.1:8000

---

## Modo Produção

```bash
    gunicorn --bind 0.0.0.0:8000 app:app
```
---

# 6. Referência da API

## **POST /processar-documento**

Tipo: `multipart/form-data`

| Campo               | Tipo   | Obrigatório | Descrição                                          |
|---------------------|--------|-------------|----------------------------------------------------|
| arquivo             | File   | Sim         | PDF a ser processado                               |
| tipo_analise        | String | Sim         | extracao_conta ou validacao_endereco               |
| endereco_formulario | String | Opcional    | Usado apenas em validação de endereço              |
| cep_formulario      | String | Opcional    | Usado apenas em validação de endereço              |

---

### Exemplo — Extração de Fatura

Requisição:

    curl -X POST "http://127.0.0.1:8000/processar-documento" \
         -F "arquivo=@/caminho/para/conta.pdf" \
         -F "tipo_analise=extracao_conta"

Resposta:

    {
      "mensagem": "Dados da fatura extraídos com sucesso.",
      "dados": {
        "valor_total": "145.50",
        "data_vencimento": "25/11/2025",
        "categoria": "Energia"
      }
    }

Erro (422):

    {
      "detail": "Dados essenciais (valor e vencimento) não foram encontrados."
    }

---

### Exemplo — Validação de Endereço

Requisição:

    curl -X POST "http://127.0.0.1:8000/processar-documento" \
         -F "arquivo=@/caminho/para/comprovante.pdf" \
         -F "tipo_analise=validacao_endereco" \
         -F "endereco_formulario=Rua das Flores, 123" \
         -F "cep_formulario=75000-123"

Sucesso (Via CEP):

    { "mensagem": "Endereço validado com sucesso via CEP." }

Sucesso (Via Logradouro):

    { "mensagem": "Endereço validado com sucesso via Logradouro." }

Falha (400):

    {
      "detail": "O endereço fornecido não corresponde ao do documento."
    }

---

# 7. Resumo dos Códigos de Erro

| Código | Causa |
|--------|-------|
| 400 | Campos obrigatórios ausentes, arquivo inválido, parâmetros insuficientes |
| 422 | Dados essenciais (valor/vencimento) não encontrados |
| 500 | Erro interno, falha no OCR ou infraestrutura |

---

# 8. Limitações e Próximos Passos

## Limitações Atuais

- Não processa PDFs protegidos por senha  
- Não processa texto manuscrito  
- OCR perde precisão com imagens tortas, borradas ou mal iluminadas  

## Melhorias Futuras (Roadmap)

- Adicionar endpoint `/health`  
- Suporte a imagens (JPG, PNG)  
- Cache de resultados (Redis)  
- Regras mais avançadas de categorização  

---
