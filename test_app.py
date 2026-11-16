import html
from datetime import datetime

def validar_data_nascimento(data_str):
    try:
        datetime.strptime(data_str, "%d/%m/%Y")
        return True
    except ValueError:
        return False

def sanitizar_texto(texto):
    return html.escape(texto.strip())

def test_validacao_data_rf01():
    assert validar_data_nascimento("15/11/1995") is True
    assert validar_data_nascimento("32/13/2026") is False

def test_sanitizacao_xss_rnf02():
    entrada_maliciosa = "<script>alert('xss')</script>"
    assert "<script>" not in sanitizar_texto(entrada_maliciosa)
