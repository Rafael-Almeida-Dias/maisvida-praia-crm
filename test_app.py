from app import (
    normalizar_data,
    sanitizar_xss,
    validar_dados_aluno,
    validar_data_nascimento,
)


def test_validacao_data_rf01():
    # Datas válidas com barras, hífen ou apenas números (pós-feedback da comunidade)
    assert validar_data_nascimento("15/11/1995") is True
    assert validar_data_nascimento("15-11-1995") is True
    assert validar_data_nascimento("15111995") is True
    assert normalizar_data("15111995") == "15/11/1995"
    assert normalizar_data("15-11-1995") == "15/11/1995"

    # Datas inválidas ou impossíveis no calendário (RF01)
    assert validar_data_nascimento("32/13/2026") is False
    assert validar_data_nascimento("00/00/0000") is False
    assert validar_data_nascimento("") is False

    # Validação completa de formulário de aluno
    assert validar_dados_aluno("Lucas Mendes", "15/11/1995", "21988887777") == []
    assert len(validar_dados_aluno("", "32/13/2026", "123")) == 3


def test_sanitizacao_xss_rnf02():
    # Garante bloqueio de payloads XSS conforme diretriz OWASP A03:2021 (RNF02)
    entrada_maliciosa = "<script>alert('xss')</script>"
    resultado = sanitizar_xss(entrada_maliciosa)
    assert "<script>" not in resultado
    assert "&lt;script&gt;" in resultado
