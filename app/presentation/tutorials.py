"""Tutoriais do menu "Tutoriais" — um guia curto por recurso.

O tour de boas-vindas (onboarding.py) ensina o FLUXO inteiro uma vez; aqui
cada entrada ensina UM recurso, sob demanda, para quem já usa o programa e
travou num ponto específico ("como faço a marca de registro?").

Reusa o mesmo overlay do tour (véu escuro + balão sobre o controle), só que
sem marcar o tour de boas-vindas como visto.

Por que os alvos usam getattr(..., None): o painel é montado em pedaços e
alguns controles só existem depois que há arquivo na biblioteca. Alvo
ausente ou escondido vira balão centralizado (o TourOverlay já trata), então
um tutorial nunca quebra por causa de um widget que não está na tela.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QToolButton

from app.presentation.onboarding import TourStep

# gerado por assets/make_exemplo.py e versionado junto do app
_ARQUIVO_EXEMPLO = "assets/exemplo/exemplo-printnest.pdf"


def caminho_exemplo():
    """PDF de exemplo do tutorial guiado (None se não veio no pacote).

    Vive em assets/, que o PyInstaller empacota inteira — então o mesmo
    caminho vale rodando do código e do .exe instalado."""
    from app.shared.resources import resource_path

    caminho = resource_path(_ARQUIVO_EXEMPLO)
    return caminho if caminho.exists() else None


def _sinal(window, name, sinal):
    """Sinal `sinal` do widget `name` da janela, ou None se ele não existe.

    None faz o passo virar narrado (com "Próximo") em vez de mão na massa —
    é a saída segura para um controle que mudou de nome ou não foi montado."""
    widget = getattr(window, name, None)
    if widget is None:
        return None
    return getattr(widget, sinal, None)


def guiado(window) -> list[TourStep]:
    """Tutorial guiado: o aluno FAZ o fluxo com o arquivo de exemplo.

    Os alvos aqui usam getattr direto (sem filtrar por visível, ao contrário
    de _alvo): a barra da Faca só aparece depois que há peça na chapa, e o
    TourOverlay já resolve a posição do buraco na hora de MOSTRAR o passo —
    quando o controle já está na tela."""
    def w(name):
        return getattr(window, name, None)

    return [
        TourStep(
            None, "Vamos fazer um adesivo, do zero",
            "Coloquei um arquivo de exemplo na sua biblioteca: um adesivo "
            "redondo de 9 × 9 cm, com duas artes. Em quatro passos você leva "
            "ele até o arquivo pronto para a impressora e para a máquina de "
            "corte.\n\n"
            "Faça você mesmo. Eu aviso o que clicar.",
        ),
        TourStep(
            w("_btn_place"), "1. Coloque na chapa",
            "O arquivo está na biblioteca, mas ainda não está na produção. "
            "Clique em Colocar na chapa.",
            espera=_sinal(window, "_btn_place", "clicked"),
        ),
        TourStep(
            w("_view"), "Duas peças de um arquivo só",
            "As duas páginas do PDF viraram duas peças, já encaixadas na "
            "chapa. É assim com qualquer PDF: cada página vira uma peça, e o "
            "PrintNest aproveita o material sozinho.",
        ),
        TourStep(
            w("_ct_gerar"), "2. Gere a faca",
            "Agora o contorno de corte. Clique no botão azul Gerar Faca.",
            espera=_sinal(window, "_ct_gerar", "clicked"),
        ),
        TourStep(
            w("_ct_mode"), "3. Escolha Contorno justo",
            "Repare que a borda do adesivo é ondulada. Abra o Tipo de faca e "
            "escolha Contorno justo: a linha de corte vai abraçar cada onda "
            "da arte, em vez de passar reto por fora.\n\n"
            "É esse ajuste que separa um adesivo recortado na forma de um "
            "adesivo quadrado.",
            espera=_sinal(window, "_ct_mode", "currentIndexChanged"),
            quando=lambda: (
                getattr(window, "_ct_mode", None) is not None
                and window._ct_mode.currentData() == "contour"
            ),
        ),
        TourStep(
            w("_view"), "Viu a diferença?",
            "A faca agora segue o desenho, onda por onda. Compare com o "
            "Retângulo (corte reto) se quiser ver os dois lado a lado.",
        ),
        TourStep(
            w("_ct_offset"), "4. Experimente a sangria",
            "Sangria afasta a faca da arte. Suba para 2 mm e veja a linha "
            "abrir em volta do adesivo. É o que evita cortar a arte quando a "
            "máquina desalinha um fio.",
            espera=_sinal(window, "_ct_offset", "valueChanged"),
        ),
        TourStep(
            w("_ribbon"), "Pronto para produzir",
            "É só isso. Ctrl+E abre o Centro de Exportação: de lá saem o PDF "
            "de impressão, com as marcas de registro, e o DXF de corte, um "
            "casando com o outro.",
        ),
    ]


def _alvo(window, *names):
    """Função que devolve o 1º widget VISÍVEL entre os nomes dados.

    Devolve função, não widget: o TourOverlay resolve na hora de mostrar o
    passo, depois que o `preparar` abriu a aba onde o controle mora. Resolver
    na montagem era o defeito antigo (controle em sub-aba fechada virava None
    e o balão só centralizava, sem apontar nada)."""
    def resolver():
        for name in names:
            widget = getattr(window, name, None)
            if widget is not None and widget.isVisible():
                return widget
        return None
    return resolver


def _botao_da_acao(window, name: str):
    """Função que devolve o botão da RIBBON que dispara aquela QAction.

    Modo Corte e Centro de Exportação não moram em menu: são botões da barra
    de cima. Procurar pela ação evita apontar um caminho que não existe. Este
    tutorial chegou a mandar o usuário abrir "Ferramentas → Modo Corte", e o
    Modo Corte nunca esteve nesse menu."""
    def resolver():
        acao = getattr(window, name, None)
        if acao is None:
            return None
        for btn in window.findChildren(QToolButton):
            if btn.defaultAction() is acao and btn.isVisible():
                return btn
        return None
    return resolver


def _sinal_de_acao(window, name: str):
    """Sinal `triggered` de uma QAction da janela, ou None se ela não existe."""
    acao = getattr(window, name, None)
    return None if acao is None else acao.triggered


def _sub_aba(window, indice: int):
    """Função que devolve o botão da sub-aba (Produção/Acabamento/Registro).

    São uma LISTA (_doc_nav_btns), por isso não dá para pegar por nome."""
    def resolver():
        botoes = getattr(window, "_doc_nav_btns", None) or []
        if indice < len(botoes) and botoes[indice].isVisible():
            return botoes[indice]
        return None
    return resolver


def _abrir_documento(window, secao: int):
    """Abre a aba Documento na sub-aba pedida (0 Produção, 1 Acabamento,
    2 Registro), para o controle do passo estar na tela quando o balão apontar."""
    def preparar():
        window._props_tabs.setCurrentIndex(0)
        window._show_doc_section(secao)
    return preparar


def _faca(window) -> list[TourStep]:
    return [
        TourStep(
            None, "A faca é o contorno de corte",
            "É a linha que a sua máquina segue para recortar a peça. O "
            "PrintNest cria essa linha sozinho a partir da arte. Você só "
            "ajusta como ela deve sair.",
        ),
        TourStep(
            _alvo(window, "_ct_mode", "_faca_mode"), "1. Tipo de faca",
            "Automático segue o desenho da arte. Contorno justo abraça a "
            "silhueta. Retângulo corta na caixa da peça. Faca do cliente usa "
            "a linha magenta que já veio no arquivo, e tem tutorial só dela.",
            preparar=_abrir_documento(window, 0),
        ),
        TourStep(
            _alvo(window, "_ct_offset", "_offset"), "2. Sangria (offset)",
            "Afasta a faca da arte para fora (valor positivo) ou puxa para "
            "dentro (negativo). Positivo evita cortar a arte quando a "
            "máquina desalinha um fio; 0 corta exatamente no contorno.",
            preparar=_abrir_documento(window, 0),
        ),
        TourStep(
            _alvo(window, "_ct_smooth", "_ct_nodes", "_faca_nodes"),
            "3. Suavizar e nós",
            "Suavizar arredonda os cantinhos do contorno detectado. Nós da "
            "faca controla quantos pontos a linha terá. Menos nós, corte "
            "mais rápido e macio na máquina.",
            preparar=_abrir_documento(window, 0),
        ),
        TourStep(
            _alvo(window, "_ct_gerar", "_prop_bar"), "4. Gerar",
            "É este o botão azul. Com uma peça selecionada, os ajustes valem "
            "só para o arquivo dela; sem seleção, valem para o documento "
            "inteiro.\n\n"
            "A barra da Faca só aparece quando há arquivo na produção.",
        ),
    ]


def _faca_do_cliente(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Quando a faca já vem no arquivo",
            "Muito arquivo de gráfica já traz a linha de corte desenhada em "
            "MAGENTA 100% (só traço, sem preenchimento), o mesmo que o RIP "
            "chama de CutContour. O PrintNest lê essa linha e usa como faca.",
        ),
        TourStep(
            _alvo(window, "_ct_mode", "_faca_mode"), "Escolha Faca do cliente",
            "Abra o Tipo de faca e escolha Faca do cliente (vetor do PDF).\n\n"
            "Com esse tipo, o desenho do cliente é a verdade: nada de "
            "simplificar, suavizar ou reduzir nós. Sai exatamente a faca que "
            "ele mandou. Era o que fazia o cliente reclamar de \"outra faca\".",
            espera=_sinal(window, "_faca_mode", "currentIndexChanged"),
            quando=lambda: (
                getattr(window, "_faca_mode", None) is not None
                and window._faca_mode.currentData() == "vector"
            ),
            preparar=_abrir_documento(window, 0),
        ),
        TourStep(
            _alvo(window, "_view"), "A linha magenta não imprime",
            "Ela é instrução de corte, não arte. O PrintNest a remove do "
            "preview e do PDF de impressão automaticamente, mas ela continua "
            "valendo como faca no arquivo de corte.",
        ),
        TourStep(
            _alvo(window, "_ct_offset", "_offset", "_ct_radius"), "Ajustes opcionais",
            "Sangria e raio dos cantos continuam disponíveis se você QUISER "
            "mexer. Se não mexer, a faca sai igualzinha à do arquivo.",
            preparar=_abrir_documento(window, 0),
        ),
    ]


def _registro(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Marcas de registro",
            "São os alvos que a máquina de corte procura para saber onde a "
            "chapa está. Sem elas o corte sai torto em relação à impressão.\n\n"
            "Vou te mostrar onde ficam.",
        ),
        TourStep(
            _sub_aba(window, 2), "Aqui: painel Documento, sub-aba Registro",
            "Já abri para você. É nesta sub-aba que as marcas são configuradas.",
            preparar=_abrir_documento(window, 2),
        ),
        TourStep(
            _alvo(window, "_reg_type"), "Escolha o tipo da sua máquina",
            "Cada máquina lê um padrão diferente. Abra a lista e escolha o da "
            "sua: as marcas aparecem na chapa na hora, já nas posições certas.\n\n"
            "Escolha uma opção para seguir.",
            espera=_sinal(window, "_reg_type", "currentIndexChanged"),
            preparar=_abrir_documento(window, 2),
        ),
        TourStep(
            _alvo(window, "_view"), "Confira antes de exportar",
            "As marcas aparecem no preview da chapa. Vale conferir se nenhuma "
            "peça está por cima delas: a leitora precisa enxergar o alvo "
            "limpo.",
        ),
        TourStep(
            _botao_da_acao(window, "_act_export_center"),
            "Elas vão no arquivo exportado",
            "O PDF de impressão sai com as marcas impressas e o arquivo de "
            "corte sai com elas na mesma coordenada. É isso que casa os dois.\n\n"
            "A exportação é por aqui, no Centro de Exportação.",
        ),
    ]


def _modo_corte(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Modo Corte (laser / CNC)",
            "É um fluxo SEPARADO, para quem corta sem impressão: você monta "
            "só as peças de corte na chapa e exporta o vetor.\n\n"
            "Vou te mostrar onde ele fica.",
        ),
        TourStep(
            _botao_da_acao(window, "_act_modo_corte"), "O botão é este",
            "Fica na barra de cima, no grupo Corte. Ele abre numa janela "
            "própria, separada da produção de impressão.",
        ),
        TourStep(
            None, "O que você faz lá dentro",
            "Importa SVG, PDF ou texto; o botão Organizar roda o encaixe e "
            "aproveita o máximo da chapa (em segundo plano, com barra de "
            "progresso). Não gostou? Arraste as peças e gire com as setas: o "
            "ajuste manual é respeitado na exportação.\n\n"
            "No fim sai o DXF, cada peça um contorno fechado, do jeito que a "
            "controladora espera.",
        ),
        TourStep(
            _botao_da_acao(window, "_act_modo_corte"), "Abra agora",
            "Clique no Modo Corte. O tutorial termina aqui, para você "
            "explorar a janela à vontade.",
            espera=_sinal_de_acao(window, "_act_modo_corte"),
        ),
    ]


def _paginas_e_recorte(window) -> list[TourStep]:
    return [
        TourStep(
            _alvo(window, "_btn_pages"), "Escolher páginas do PDF",
            "PDF com 50 páginas e você só quer 3? Abra Páginas do PDF... e "
            "marque quais entram na produção. As outras nem são importadas.",
        ),
        TourStep(
            _alvo(window, "_btn_crop"), "Recortar bordas",
            "Recortar páginas ou imagem... corta as bordas em milímetros. "
            "Serve para tirar marcas de corte, sangria ou moldura que vieram "
            "no arquivo e não fazem parte da arte.",
        ),
        TourStep(
            _alvo(window, "_table"), "Botão direito na peça",
            "O menu do botão direito na peça (ou na linha da biblioteca) tem "
            "os mesmos atalhos, sem precisar procurar no painel.",
        ),
        TourStep(
            None, "O arquivo original nunca é alterado",
            "O recorte é aplicado numa cópia temporária. Seu PDF no disco "
            "continua intacto. Dá para desfazer o recorte quando quiser.",
        ),
    ]


def _exportar(window) -> list[TourStep]:
    return [
        TourStep(
            _botao_da_acao(window, "_act_export_center"), "O botão é este",
            "Fica na barra de cima, no grupo Exportar. Também está no menu "
            "Arquivo, e o atalho é Ctrl+E.\n\n"
            "Um lugar só para sair com tudo: escolha quais chapas exportar "
            "(com miniatura para conferir) e o formato.",
        ),
        TourStep(
            None, "PDF de impressão",
            "É o que vai para a impressora: a arte nas posições da chapa, com "
            "as marcas de registro e SEM a linha magenta da faca.",
        ),
        TourStep(
            None, "DXF / PDF de faca",
            "É o que vai para a máquina de corte: só os contornos, na mesma "
            "coordenada do PDF de impressão. Um casa com o outro.",
        ),
        TourStep(
            None, "Exportar só o que está selecionado",
            "Selecionou uma peça e apertou Ctrl+E? Dá para exportar só ela, "
            "útil para reposição sem refazer a chapa inteira.",
        ),
        TourStep(
            _botao_da_acao(window, "_act_export_center"), "Abra agora",
            "Clique no Centro de Exportação (ou aperte Ctrl+E). O tutorial "
            "termina aqui.",
            espera=_sinal_de_acao(window, "_act_export_center"),
        ),
    ]


# (rótulo no menu, ícone, construtor dos passos). A ordem é a do menu.
# O ícone tem de existir em assets/icons — nome inexistente vira ícone VAZIO
# (icons.icon não falha), o que passa despercebido até alguém olhar o menu.
TUTORIAIS: list[tuple[str, str, Callable[[object], list[TourStep]]]] = [
    ("A faca (contorno de corte)", "scissors", _faca),
    ("Faca do cliente (linha magenta)", "nodes", _faca_do_cliente),
    ("Marcas de registro", "radio-on", _registro),
    ("Modo Corte (laser / CNC)", "grid-3x3", _modo_corte),
    ("Páginas do PDF e recorte", "file-text", _paginas_e_recorte),
    ("Exportar impressão e corte", "download", _exportar),
]
