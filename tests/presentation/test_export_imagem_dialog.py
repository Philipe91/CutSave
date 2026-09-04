"""Tela de exportacao em imagem (estilo Corel): formato, DPI, espaco de cor,
perfil e qualidade numa tela so.

O que estes testes protegem e a REGRA, nao o desenho: PNG nao pode oferecer
CMYK (limite do formato, e prometer o que o arquivo nao guarda e pior do que
nao oferecer), e a escolha do operador tem que chegar inteira no exportador.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.infrastructure.color_profiles import (  # noqa: E402
    caminho_do_perfil_padrao,
    perfis_cmyk_do_sistema,
)
from app.presentation.panels.dpi_dialog import ExportarImagemDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dlg(qapp, **kw):
    return ExportarImagemDialog(None, 200.0, 300.0, kw.pop("fmt", "jpeg"), 150, **kw)


def test_png_nunca_oferece_cmyk(qapp):
    """PNG nao guarda CMYK: a tela nao pode deixar escolher o que nao sai."""
    dlg = _dlg(qapp, fmt="png", color_space_inicial="cmyk")
    assert dlg.color_space() == "rgb"
    assert not dlg._cor._espaco.isEnabled()
    assert "PNG" in dlg._cor._nota.text()


def test_jpeg_deixa_escolher_cmyk(qapp):
    if not perfis_cmyk_do_sistema():
        pytest.skip("maquina sem perfil CMYK instalado")
    dlg = _dlg(qapp, fmt="jpeg", color_space_inicial="cmyk")
    assert dlg.color_space() == "cmyk"
    assert dlg.icc_path()


def test_arte_cmyk_abre_a_tela_em_cmyk(qapp):
    """Sugestao: se a arte e CMYK, o padrao ja e o espaco dela."""
    if not perfis_cmyk_do_sistema():
        pytest.skip("maquina sem perfil CMYK instalado")
    dlg = _dlg(qapp, fmt="jpeg", color_space_inicial="rgb", sugerir_cmyk=True)
    assert dlg.color_space() == "cmyk"


def test_padrao_continua_rgb(qapp):
    """Sem arte CMYK e sem preferencia salva, nada muda para quem ja usava."""
    dlg = _dlg(qapp, fmt="jpeg")
    assert dlg.color_space() == "rgb"


def test_a_tela_avisa_o_que_o_cmyk_nao_faz(qapp):
    """A conversao nao devolve a tinta original — e isso precisa estar dito
    ANTES de imprimir, nao depois."""
    if not perfis_cmyk_do_sistema():
        pytest.skip("maquina sem perfil CMYK instalado")
    dlg = _dlg(qapp, fmt="jpeg", color_space_inicial="cmyk")
    assert "PDF" in dlg._cor._nota.text()


def test_qualidade_e_devolvida(qapp):
    dlg = _dlg(qapp, fmt="jpeg", quality_inicial=60)
    assert dlg.quality() == 60


def test_perfil_salvo_e_reaberto(qapp):
    """A escolha do perfil persiste entre exportacoes."""
    padrao = caminho_do_perfil_padrao()
    if not padrao:
        pytest.skip("maquina sem perfil CMYK instalado")
    dlg = _dlg(qapp, fmt="jpeg", color_space_inicial="cmyk", icc_inicial=padrao)
    assert dlg.icc_path() == padrao


def test_troca_de_formato_reflete_no_getter(qapp):
    dlg = _dlg(qapp, fmt="jpeg")
    dlg._formato.setCurrentIndex(1)  # PNG
    assert dlg.formato() == "png"
    assert dlg.color_space() == "rgb"


# ---- Centro de Exportacao: a porta que o cliente usa de verdade ----
#
# A primeira versao da opcao de cor so existia no dialogo do menu
# "Exportar Imagem". O Centro de Exportacao chama export_image(dpi=...) com o
# DPI ja preenchido, e como o dialogo so aparece quando dpi e None, aquele
# caminho passava RETO pelas opcoes — o cliente abriu o programa e nao achou
# nada (03/09/2026). Estes testes existem para isso nao voltar.

def test_widget_de_cor_funciona_sem_saber_o_formato(qapp):
    """No Centro de Exportacao o PNG/JPEG so e decidido depois, ao nomear o
    arquivo: a tela nao pode desabilitar CMYK por causa disso."""
    from app.presentation.panels.dpi_dialog import OpcoesDeCor

    if not perfis_cmyk_do_sistema():
        pytest.skip("maquina sem perfil CMYK instalado")
    w = OpcoesDeCor(color_space_inicial="cmyk", formato_conhecido=False)
    assert w.color_space() == "cmyk"
    assert w._espaco.isEnabled()
    assert "PNG" in w._nota.text()  # avisa que PNG sairia em RGB


def test_centro_de_exportacao_repassa_a_cor_escolhida(qapp):
    """O painel tem que ENTREGAR a escolha para o export_image — e com os
    nomes exatos que export_image espera."""
    import inspect

    from app.presentation.main_window import ExportCenterDialog, MainWindow
    from app.presentation.panels.dpi_dialog import OpcoesDeCor

    if not perfis_cmyk_do_sistema():
        pytest.skip("maquina sem perfil CMYK instalado")

    class _Painel:  # so precisa do widget: o metodo nao toca em mais nada
        _opt_cor = OpcoesDeCor(color_space_inicial="cmyk", quality_inicial=70,
                               formato_conhecido=False)

    kwargs = ExportCenterDialog._opcoes_de_cor(_Painel())
    assert kwargs["color_space"] == "cmyk"
    assert kwargs["quality"] == 70
    assert kwargs["icc_path"]
    # os nomes tem que casar com a assinatura, senao estoura so na exportacao
    aceitos = set(inspect.signature(MainWindow.export_image).parameters)
    assert set(kwargs) <= aceitos


def test_painel_do_centro_cabe_sem_esmagar_os_campos(qapp):
    """Layout do Centro de Exportacao: os campos nao podem sair desenhados uns
    por cima dos outros.

    Aconteceu em 03/09/2026: o dialogo tinha setMinimumSize(720, 480) e minimo
    EXPLICITO de altura ganha do minimo calculado pelo layout — com os
    controles de cor o layout passou a pedir ~613px, o Qt manteve 480 e
    espremeu tudo. O teste olha a conta, nao o pixel: a altura do dialogo tem
    que ser pelo menos a que o layout pede.
    """
    from app.presentation.panels.dpi_dialog import OpcoesDeCor

    w = OpcoesDeCor(color_space_inicial="cmyk", formato_conhecido=False,
                    compacto=True)
    w.show()
    try:
        qapp.processEvents()
        # cada campo visivel ocupa a sua propria faixa vertical
        campos = [w._espaco, w._campo_perfil, w._qualidade]
        faixas = sorted(
            (c.mapTo(w, c.rect().topLeft()).y(), c.height())
            for c in campos if c.isVisible()
        )
        for (y0, h0), (y1, _) in zip(faixas, faixas[1:]):
            assert y1 >= y0 + h0, "campos do painel de cor sobrepostos"
        assert w.height() >= w.minimumSizeHint().height()
    finally:
        w.hide()
