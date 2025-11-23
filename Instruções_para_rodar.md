# Instruções para Execução - Qota OCR Service

Este documento detalha os passos necessários para configurar e executar o microsserviço de OCR do Qota em um ambiente de desenvolvimento. A correta configuração das dependências externas é **crucial** para o funcionamento do sistema.

### Pré-requisitos Globais

Garanta que você tem os seguintes softwares instalados:

* **[Git](https://git-scm.com/downloads)**: Para clonar o repositório.
* **[Python](https://www.python.org/downloads/)**: Versão `3.9` ou superior. Ao instalar, marque a opção **"Add Python to PATH"**.

---

### ⚙️ 1. Instalação das Dependências de Sistema (Obrigatório)

O serviço de OCR depende de ferramentas de sistema que precisam ser instaladas e configuradas **antes** da instalação das bibliotecas Python.

#### **Instrução para Windows (Leitura Obrigatória)**

A instalação no Windows requer três componentes principais:

##### **A. Tesseract-OCR (Motor de OCR)**

1.  **Baixar:** Baixe o instalador `tesseract-ocr-w64-setup-*.exe` a partir de [**Tesseract at UB Mannheim**](https://github.com/UB-Mannheim/tesseract/wiki).
2.  **Instalar:**
    * Execute o instalador.
    * Na tela "Select Components", marque a opção **"Portuguese"** para adicionar o suporte ao idioma português.
    * **IMPORTANTE:** Se a opção **"Add Tesseract to the system PATH"** estiver disponível, marque-a.

3.  **Configurar o PATH (Se a opção acima falhou):**
    * Muitas vezes, a opção de adicionar ao PATH não funciona. Para garantir, adicione manualmente:
    * Pesquise por **"Editar as variáveis de ambiente do sistema"** no menu Iniciar.
    * Clique em "Variáveis de Ambiente...".
    * Na seção "Variáveis do sistema", encontre e selecione a variável `Path` e clique em "Editar".
    * Clique em "Novo" e adicione o caminho da pasta onde o Tesseract foi instalado. (Por padrão: `C:\Program Files\Tesseract-OCR`)
    * Clique em "OK" em todas as janelas.

##### **B. Poppler (Leitor de PDF)**

1.  **Baixar:** Baixe a versão mais recente do [**Poppler for Windows**](https://github.com/oschwartz10612/poppler-windows/releases/). Procure pelo arquivo `Release-*.zip`.
2.  **Instalar:**
    * Extraia o conteúdo do arquivo `.zip` para uma pasta permanente (ex: `C:\Program Files\poppler`).
    * Copie o caminho da pasta `bin` que está dentro do diretório que você extraiu (ex: `C:\Program Files\poppler\bin`).
3.  **Configurar o PATH:**
    * Siga os mesmos passos do Tesseract para **"Editar as variáveis de ambiente do sistema"**.
    * Adicione um **novo** caminho ao seu `Path` do sistema, colando o caminho da pasta `bin` do Poppler.

##### **C. Visual Studio Build Tools (Compilador C++)**

1.  **Baixar:** Esta é a dependência mais crítica, necessária para a biblioteca `PyMuPDF`.
    * Vá para a página de downloads do Visual Studio: [**visualstudio.microsoft.com/downloads/**](https://visualstudio.microsoft.com/downloads/).
    * Role a página até encontrar "Ferramentas para Visual Studio" (ou "Tools for Visual Studio").
    * Encontre **"Build Tools for Visual Studio 2022"** e clique em "Baixar".
2.  **Instalar:**
    * Execute o instalador `vs_BuildTools.exe`.
    * Na aba **"Cargas de Trabalho"**, marque **exatamente** esta opção: **"Desenvolvimento para desktop com C++"**.
    * Clique em "Instalar". (Isso pode levar algum tempo e consumir alguns GB de espaço).
3.  **Reiniciar:** Após a instalação, **reinicie o seu computador**.

---

### 🚀  Configuração e Execução do Projeto

Após instalar as 3 dependências de sistema (Tesseract, Poppler, VS Build Tools) e reiniciar, você pode configurar o projeto Python.

#### ** Clonar o Repositório**

```bash
git clone [https://github.com/filipetocchio/Qota-OCR-Service.git](https://github.com/filipetocchio/Qota-OCR-Service.git)
cd Qota-OCR-Service
```

####  Configuração do Microsserviço de OCR (Python)

Este serviço precisa estar rodando para que a validação de documentos funcione.

```bash
# Navegue até a pasta do serviço
cd  Qota-OCR-Service

# Crie e ative um ambiente virtual
python -m venv venv

# No Windows:
.\venv\Scripts\activate

# No Linux/macOS:
source venv/bin/activate


python -m pip install --upgrade pip

# Instale as dependências
pip install -r requirements.txt
```

**Nota:** Se a instalação do PyMuPDF falhar com um erro de "metadata", significa que as "Build Tools C++" (Passo 1.C) não foram instaladas corretamente.

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



#### Baixar o Modelo de Linguagem (spaCy)


```bash
# Precisamos baixar o modelo de português para a extração de dados por IA.
python -m spacy download pt_core_news_lg

# E. Iniciar o Servidor
python app.py

```

> **Nota:** O servidor do OCR irá rodar na porta `8000`.
