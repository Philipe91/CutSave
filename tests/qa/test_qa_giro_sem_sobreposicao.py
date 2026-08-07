"""Peça girada não pode virar peça em cima de peça (07/08/2026).

Em 07/08 liguei a rotação automática do encaixe do Modo Impressão depois de
auditar os quatro consumidores que DESENHAM a peça (preview, PDF, faca, DXF).
O Philipe testou num projeto real e apareceu peça sobreposta.

O motor não era o culpado: ele nunca sobrepõe. O buraco estava no caminho de
volta CANVAS -> MODELO — uma dúzia de lugares recriava o PlacedItem a partir
da cena SEM o giro:

    PlacedItem(piece.artwork_id, Point2D(px, py))   # giro perdido

Mover, duplicar, repetir em grade, excluir, copiar/colar, exportar seleção e
restaurar o arranjo salvo do .printnest. Cada um deles devolvia a peça deitada
para a posição EM PÉ na mesma coordenada, por cima da vizinha. E como o
arranjo salvo também não guardava giro, o estrago sobrevivia a salvar e
reabrir.

Estes testes cobrem o caminho que faltava. Auditar quem desenha não bastou;
tem que auditar quem RECONSTRÓI.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.application.footprint import tamanho_ocupado
from app.domain.geometry import Point2D
from app.domain.model.placement import PlacedItem

EPS = 1e-6


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def _caixas(layout, por_id):
    """Retângulo REALMENTE ocupado por cada peça (o mesmo que preview, PDF,
    faca e DXF usam para desenhar)."""
    caixas = []
    for it in layout.items:
        art = por_id.get(it.artwork_id)
        if art is None:
            continue
        oc = tamanho_ocupado(art, it.rotation)
        caixas.append((it.position.x, it.position.y,
                       it.position.x + oc.width, it.position.y + oc.height))
    return caixas


def sobreposicoes(layout, por_id):
    caixas = _caixas(layout, por_id)
    ruins = []
    for i, a in enumerate(caixas):
        for b in caixas[i + 1:]:
            if (a[0] < b[2] - EPS and b[0] < a[2] - EPS
                    and a[1] < b[3] - EPS and b[1] < a[3] - EPS):
                ruins.append((a, b))
    return ruins


# ---- o contrato do PieceItem ----------------------------------------------

def test_a_peca_da_tela_carrega_o_proprio_giro(qapp):
    """Sem isto, todo caminho tela->modelo perde o giro em silêncio."""
    from app.presentation.main_window import PieceItem

    peca = PieceItem(100.0, 50.0, artwork_id="a0", name="a0", art_size=None,
                     sheet_index=0, dx=0.0, dy=0.0, giro=90)
    assert peca.giro == 90


def test_giro_da_peca_e_normalizado(qapp):
    from app.presentation.main_window import PieceItem

    peca = PieceItem(100.0, 50.0, artwork_id="a0", name="a0", art_size=None,
                     sheet_index=0, dx=0.0, dy=0.0, giro=450)
    assert peca.giro == 90


def test_sem_giro_o_padrao_continua_zero(qapp):
    from app.presentation.main_window import PieceItem

    peca = PieceItem(100.0, 50.0, artwork_id="a0", name="a0", art_size=None,
                     sheet_index=0, dx=0.0, dy=0.0)
    assert peca.giro == 0


# ---- detector de sobreposição ---------------------------------------------

class _Arte:
    """Arte mínima: só o que tamanho_ocupado precisa."""

    def __init__(self, w, h):
        from app.domain.geometry import Size
        from app.domain.model.artwork import ArtKind, Artwork, FileFormat

        self._art = Artwork(id="a0", name="a0", file_format=FileFormat.PDF,
                            size=Size(w, h), kind=ArtKind.RETANGULAR)

    @property
    def art(self):
        return self._art


def _layout_fake(itens):
    class _L:
        def __init__(self, items):
            self.items = items
    return _L(itens)


def test_o_detector_acha_a_sobreposicao_que_o_bug_causava():
    """Reproduz o defeito: peça de 300x100 encaixada DEITADA (ocupa 100x300)
    e a vizinha logo ao lado em x=110. Se o giro se perder, a primeira volta a
    ocupar 300 de largura e invade a segunda."""
    art = _Arte(300.0, 100.0).art
    por_id = {"a0": art}
    com_giro = _layout_fake([
        PlacedItem("a0", Point2D(0.0, 0.0), 90),
        PlacedItem("a0", Point2D(110.0, 0.0), 90),
    ])
    assert sobreposicoes(com_giro, por_id) == []

    giro_perdido = _layout_fake([
        PlacedItem("a0", Point2D(0.0, 0.0)),        # <- giro caiu
        PlacedItem("a0", Point2D(110.0, 0.0), 90),
    ])
    assert sobreposicoes(giro_perdido, por_id), (
        "o detector precisa pegar exatamente este caso — foi ele que passou"
    )


def test_pecas_encostadas_sem_giro_nao_contam_como_sobreposicao():
    """Borda com borda é encaixe justo, não sobreposição."""
    art = _Arte(100.0, 50.0).art
    layout = _layout_fake([
        PlacedItem("a0", Point2D(0.0, 0.0)),
        PlacedItem("a0", Point2D(100.0, 0.0)),
    ])
    assert sobreposicoes(layout, {"a0": art}) == []


# ---- o ciclo completo: salvar e reabrir -----------------------------------

def test_o_arranjo_salvo_guarda_e_devolve_o_giro():
    """O .printnest tem de carregar o giro por peça; sem isso, o estrago
    sobrevive a salvar e reabrir."""
    from app.application.footprint import giro_reto

    item = {"id": "a0", "x": 10.0, "y": 20.0, "giro": 90}
    assert giro_reto(item.get("giro", 0)) == 90


def test_projeto_antigo_sem_a_chave_abre_com_giro_zero():
    """Chave aditiva: projeto salvo antes dela não pode quebrar."""
    from app.application.footprint import giro_reto

    item = {"id": "a0", "x": 10.0, "y": 20.0}
    assert giro_reto(item.get("giro", 0)) == 0


@pytest.mark.parametrize("valor", [None, "abc", 37.5, float("nan")])
def test_giro_corrompido_no_arquivo_vira_zero(valor):
    """Projeto editado à mão ou corrompido não pode derrubar a abertura."""
    from app.application.footprint import giro_reto

    assert giro_reto(valor) == 0


# ---- o ciclo REAL na janela ------------------------------------------------
# Este e o teste que teria pegado o bug. Os de cima provam pecas do mecanismo;
# este roda o caminho de verdade: gerar com rotacao ligada, ler de volta pelo
# _effective_sheets() (o mesmo que exportacao e salvamento usam) e conferir que
# nenhuma peca ficou por cima de outra.

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz  # noqa: E402

from app.application.use_cases.export_dxf import ExportDxfUseCase  # noqa: E402
from app.application.use_cases.export_print_pdf import (  # noqa: E402
    ExportPrintPdfUseCase,
)
from app.application.use_cases.import_image import ImportImageUseCase  # noqa: E402
from app.application.use_cases.import_pdf import ImportPdfUseCase  # noqa: E402
from app.application.use_cases.run_grid_nesting import (  # noqa: E402
    RunGridNestingUseCase,
)
from app.application.use_cases.run_production_pipeline import (  # noqa: E402
    RunProductionPipelineUseCase,
)
from app.domain.nesting.max_rects import MaxRectsPacker  # noqa: E402
from app.infrastructure.exporters.dxf_exporter import DxfExporter  # noqa: E402
from app.infrastructure.exporters.pikepdf_print_exporter import (  # noqa: E402
    PikePdfPrintExporter,
)
from app.infrastructure.importers.cv2_image_importer import (  # noqa: E402
    Cv2ImageImporter,
)
from app.infrastructure.importers.pdfium_importer import PdfiumImporter  # noqa: E402
from app.infrastructure.rendering.pdfium_renderer import (  # noqa: E402
    PdfiumPageRenderer,
)
from app.presentation.main_window import MainWindow  # noqa: E402
from app.shared.config.settings import SettingsStore  # noqa: E402

MM2PT = 72.0 / 25.4


def _pdf(tmp_path, w, h, nome):
    doc = fitz.open()
    page = doc.new_page(width=w * MM2PT, height=h * MM2PT)
    page.draw_rect(page.rect, color=(0.2, 0.3, 0.9), fill=(0.2, 0.3, 0.9))
    caminho = tmp_path / nome
    doc.save(str(caminho))
    doc.close()
    return str(caminho)


def _janela_girando(tmp_path, nome="giro"):
    """Janela com a rotacao automatica LIGADA, independente do GIRO_AUTOMATICO.

    Assim o teste continua valendo quando o interruptor estiver desligado — e
    volta a falhar na hora em que alguem religar sem consertar o caminho."""
    pasta = tmp_path / nome
    pasta.mkdir(exist_ok=True)
    store = SettingsStore(pasta / "config.json")
    settings = store.load_or_create()
    w = MainWindow(
        RunProductionPipelineUseCase(
            ImportPdfUseCase(PdfiumImporter()),
            image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=pasta / "img")),
        ),
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )
    w._nesting_uc = RunGridNestingUseCase(MaxRectsPacker(allow_rotate=True))
    w._width.setValue(300.0)
    w._height.setValue(400.0)
    # pecas compridas: e onde a rotacao de fato entra
    w.add_paths([_pdf(tmp_path, 260.0, 40.0, "comprida.pdf"),
                 _pdf(tmp_path, 90.0, 90.0, "quadrada.pdf")])
    w.generate(blocking=True)
    return w


def _sem_sobreposicao(w, contexto):
    por_id = {a.id: a for a in w._result.artworks}
    for i, chapa in enumerate(w._effective_sheets()):
        ruins = sobreposicoes(chapa, por_id)
        assert not ruins, f"{contexto}: chapa {i} com {len(ruins)} sobreposição(ões)"


def test_gerar_com_rotacao_nao_sobrepoe(qapp, tmp_path):
    w = _janela_girando(tmp_path, "gerar")
    assert w._result is not None and w._result.sheets
    _sem_sobreposicao(w, "logo apos gerar")


def test_o_giro_sobrevive_a_volta_pela_tela(qapp, tmp_path):
    """_effective_sheets() reconstroi tudo a partir das PECAS da cena — e o
    caminho que perdia o giro. Comparar com o que o motor produziu."""
    w = _janela_girando(tmp_path, "volta")
    do_motor = [
        (it.artwork_id, int(float(it.rotation)))
        for chapa in w._result.sheets for it in chapa.items
    ]
    da_tela = [
        (it.artwork_id, int(float(it.rotation)))
        for chapa in w._effective_sheets() for it in chapa.items
    ]
    assert sorted(da_tela) == sorted(do_motor), "o giro se perdeu na volta"


def test_duplicar_preserva_o_giro_da_peca(qapp, tmp_path):
    """Ctrl+D SOBREPOE de proposito (deslocamento diagonal, estilo Corel), entao
    aqui nao se checa sobreposicao — checa-se que a copia herda o giro. Sem
    isso a copia de uma peca deitada nascia em pe."""
    w = _janela_girando(tmp_path, "duplicar")
    alvo = w._piece_items[0]
    giro_original = alvo.giro
    antes = len(list(w._effective_sheets()[0].items))
    alvo.setSelected(True)
    w._duplicate_selected()
    itens = [
        it for chapa in w._effective_sheets() for it in chapa.items
        if it.artwork_id == alvo.artwork_id
    ]
    assert len([i for c in w._effective_sheets() for i in c.items]) > antes
    assert all(int(float(i.rotation)) == giro_original for i in itens), (
        "a copia nasceu com giro diferente do original"
    )


def test_arranjo_salvo_devolve_o_giro(qapp, tmp_path):
    """Salvar e reabrir nao pode desfazer o giro: era assim que o estrago
    sobrevivia ao fechar o programa."""
    w = _janela_girando(tmp_path, "salvar")
    arranjo = w._arranjo_to_json()
    giros = [
        it.get("giro", 0)
        for chapa in arranjo["chapas"] for it in chapa["itens"]
    ]
    do_motor = [
        int(float(it.rotation))
        for chapa in w._effective_sheets() for it in chapa.items
    ]
    assert sorted(giros) == sorted(do_motor), "o .printnest perdeu o giro"


# ---- o liga/desliga da interface -------------------------------------------
# Ideia do Philipe (07/08): "RIP de impressora tem como habilitar e desabilitar
# a rotacao automatica". E opcao e nao padrao porque material DIRECIONAL
# (tecido, vinil com veio, papel com fibra) nao pode ter peca girada.

def _janela(tmp_path, nome):
    pasta = tmp_path / nome
    pasta.mkdir(exist_ok=True)
    store = SettingsStore(pasta / "config.json")
    settings = store.load_or_create()
    w = MainWindow(
        RunProductionPipelineUseCase(
            ImportPdfUseCase(PdfiumImporter()),
            image_uc=ImportImageUseCase(Cv2ImageImporter(cache_dir=pasta / "img")),
        ),
        ExportPrintPdfUseCase(PikePdfPrintExporter()),
        ExportDxfUseCase(DxfExporter()),
        PdfiumPageRenderer(),
        store,
        settings,
    )
    return w, store


def test_a_opcao_nasce_desligada(qapp, tmp_path):
    """Padrao conservador: quem tem material direcional nao pode ser
    surpreendido por peca girada."""
    w, _ = _janela(tmp_path, "padrao")
    assert w._auto_rotate.isChecked() is False
    assert w._nesting_uc._packer._allow_rotate is False


def test_ligar_a_opcao_troca_o_motor(qapp, tmp_path):
    w, _ = _janela(tmp_path, "ligar")
    w._auto_rotate.setChecked(True)
    assert w._nesting_uc._packer._allow_rotate is True
    w._auto_rotate.setChecked(False)
    assert w._nesting_uc._packer._allow_rotate is False


def test_a_escolha_sobrevive_a_fechar_o_programa(qapp, tmp_path):
    """Marcar e reabrir tem de voltar marcado — senao a opcao nao serve."""
    w, store = _janela(tmp_path, "persistir")
    w._auto_rotate.setChecked(True)
    assert store.load_or_create().auto_rotate is True

    w2, _ = _janela(tmp_path, "persistir")  # mesma pasta = mesmo config.json
    assert w2._auto_rotate.isChecked() is True
    assert w2._nesting_uc._packer._allow_rotate is True


def test_config_antigo_sem_a_chave_abre_desligado(qapp, tmp_path):
    """Campo aditivo: config gravado antes da opcao nao pode quebrar."""
    pasta = tmp_path / "antigo"
    pasta.mkdir()
    (pasta / "config.json").write_text('{"material_width": 1300}', encoding="utf-8")
    store = SettingsStore(pasta / "config.json")
    assert store.load_or_create().auto_rotate is False


def test_peca_que_so_cabe_deitada_entra_com_a_opcao_ligada(qapp, tmp_path):
    """O caso real do Philipe (07/08): peça 445x1450 numa chapa 1001x1992.
    Em pé, 1450 de largura passa dos 1001 e ela não cabe. Deitada, 445 cabem
    na largura e 1450 no comprimento."""
    w, _ = _janela(tmp_path, "cabe")
    w._width.setValue(1001.0)
    w._height.setValue(1992.0)
    w.add_paths([_pdf(tmp_path, 1450.0, 445.0, "larga.pdf")])

    w._auto_rotate.setChecked(False)
    w.generate(blocking=True)
    por_id = {a.id: a for a in w._result.artworks}
    coube_em_pe = all(
        tamanho_ocupado(por_id[it.artwork_id], it.rotation).width <= 1001.0 + EPS
        for chapa in w._effective_sheets() for it in chapa.items
    )
    assert not coube_em_pe, "sem girar, a peça não deveria caber na largura"

    w._auto_rotate.setChecked(True)
    w.generate(blocking=True)
    por_id = {a.id: a for a in w._result.artworks}
    for chapa in w._effective_sheets():
        for it in chapa.items:
            oc = tamanho_ocupado(por_id[it.artwork_id], it.rotation)
            assert oc.width <= 1001.0 + EPS, "girada, a peça tem de caber"
        assert sobreposicoes(chapa, por_id) == []
