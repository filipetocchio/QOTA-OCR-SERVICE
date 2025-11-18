# Todos direitos autorais reservados pelo QOTA.

"""
Configuração de Fixtures do Pytest

Este arquivo define 'fixtures' reutilizáveis para os testes da aplicação Flask.
Fixtures são funções que criam dados, conexões ou, neste caso, instâncias
da aplicação e clientes de teste.

- 'app': Cria uma instância da aplicação Flask em modo de teste.
- 'client': Cria um cliente de teste que pode fazer requisições HTTP
  (GET, POST, etc.) à aplicação, permitindo testar os endpoints.
"""

import pytest
from app import app as flask_app

@pytest.fixture
def app():
    """Cria e configura uma nova instância da aplicação para cada teste."""
    # Configura a aplicação para o modo de teste
    flask_app.config.update({
        "TESTING": True,
    })
    
    # 'yield' fornece a aplicação para o teste
    yield flask_app
    
    # Código de limpeza (opcional) viria aqui

@pytest.fixture
def client(app):
    """Cria um cliente de teste para a aplicação Flask."""
    return app.test_client()