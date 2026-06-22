import fitz
from app.tools.pdf_discovery import format_report, main


def _build_pdf(path):
    doc = fitz.open()
    page = doc.new_page(width=595.0, height=842.0)
    page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0, 0, 0))
    doc.save(str(path))
    doc.close()


def test_main_sem_argumentos_retorna_2(capsys):
    assert main([]) == 2


def test_main_arquivo_inexistente_retorna_1(capsys, tmp_path):
    assert main([str(tmp_path / "x.pdf")]) == 1
    assert "ERRO" in capsys.readouterr().err


def test_main_relatorio_de_pdf_valido(capsys, tmp_path):
    path = tmp_path / "amostra.pdf"
    _build_pdf(path)
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "Paginas: 1" in out
    assert "Vetores: sim" in out
    assert "mm" in out


def test_format_report_inclui_dimensao(tmp_path):
    from app.infrastructure.importers.pymupdf_inspector import PyMuPdfInspector

    path = tmp_path / "amostra.pdf"
    _build_pdf(path)
    texto = format_report(PyMuPdfInspector().inspect(str(path)))
    assert "Pagina 1" in texto
    assert "209" in texto  # largura A4 em mm
