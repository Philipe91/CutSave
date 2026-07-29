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

from app.presentation.onboarding import TourStep


def _alvo(window, *names):
    """1o widget existente E visível entre os nomes dados (senão None).

    Aceita vários nomes porque o mesmo assunto tem controle diferente
    conforme a aba aberta; o balão cai no centro se nenhum estiver à vista."""
    for name in names:
        widget = getattr(window, name, None)
        if widget is not None and widget.isVisible():
            return widget
    return None


def _faca(window) -> list[TourStep]:
    return [
        TourStep(
            None, "A faca é o contorno de corte",
            "É a linha que a sua máquina segue para recortar a peça. O "
            "PrintNest cria essa linha sozinho a partir da arte — você só "
            "ajusta como ela deve sair.",
        ),
        TourStep(
            _alvo(window, "_ct_mode", "_faca_mode"), "1. Tipo de faca",
            "Automático segue o desenho da arte. Retangular corta na caixa "
            "da peça. Faca do cliente usa a linha magenta que já veio no "
            "arquivo (tem um tutorial só para ela).",
        ),
        TourStep(
            _alvo(window, "_ct_offset"), "2. Sangria (offset)",
            "Afasta a faca da arte para fora (valor positivo) ou puxa para "
            "dentro (negativo). Positivo evita cortar a arte quando a "
            "máquina desalinha um fio; 0 corta exatamente no contorno.",
        ),
        TourStep(
            _alvo(window, "_ct_smooth", "_ct_nodes"), "3. Suavizar e nós",
            "Suavizar arredonda os cantinhos do contorno detectado. Nós da "
            "faca controla quantos pontos a linha terá — menos nós, corte "
            "mais rápido e macio na máquina.",
        ),
        TourStep(
            _alvo(window, "_prop_bar"), "4. Gerar",
            "Clique no botão azul GERAR FACA. Com uma peça selecionada, os "
            "ajustes valem só para o arquivo dela; sem seleção, valem para o "
            "documento inteiro.",
        ),
    ]


def _faca_do_cliente(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Quando a faca já vem no arquivo",
            "Muito arquivo de gráfica já traz a linha de corte desenhada em "
            "MAGENTA 100% (só traço, sem preenchimento) — o mesmo que o RIP "
            "chama de CutContour. O PrintNest lê essa linha e usa como faca.",
        ),
        TourStep(
            _alvo(window, "_ct_mode", "_faca_mode"), "Escolha Faca do cliente",
            "Com esse tipo, o desenho do cliente é a verdade: nada de "
            "simplificar, suavizar ou reduzir nós. Sai exatamente a faca que "
            "ele mandou — era o que fazia o cliente reclamar de \"outra faca\".",
        ),
        TourStep(
            _alvo(window, "_view"), "A linha magenta não imprime",
            "Ela é instrução de corte, não arte. O PrintNest a remove do "
            "preview e do PDF de impressão automaticamente — mas ela continua "
            "valendo como faca no arquivo de corte.",
        ),
        TourStep(
            _alvo(window, "_ct_offset", "_ct_radius"), "Ajustes opcionais",
            "Sangria e raio dos cantos continuam disponíveis se você QUISER "
            "mexer. Se não mexer, a faca sai igualzinha à do arquivo.",
        ),
    ]


def _registro(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Marcas de registro",
            "São os alvos que a máquina de corte procura para saber onde a "
            "chapa está. Sem elas o corte sai torto em relação à impressão.",
        ),
        TourStep(
            _alvo(window, "_reg_type"), "Escolha o tipo da sua máquina",
            "Cada máquina lê um padrão diferente. Escolha o da sua e as "
            "marcas aparecem na chapa na hora, já nas posições certas.",
        ),
        TourStep(
            _alvo(window, "_props_tabs", "_view"), "Confira antes de exportar",
            "As marcas aparecem no preview da chapa. Vale conferir se nenhuma "
            "peça está por cima delas — a leitora precisa enxergar o alvo "
            "limpo.",
        ),
        TourStep(
            _alvo(window, "_ribbon"), "Elas vão no arquivo exportado",
            "O PDF de impressão sai com as marcas impressas e o arquivo de "
            "corte sai com elas na mesma coordenada. É isso que casa os dois.",
        ),
    ]


def _modo_corte(window) -> list[TourStep]:
    return [
        TourStep(
            None, "Modo Corte (laser / CNC)",
            "É um fluxo SEPARADO, para quem corta sem impressão: você monta "
            "só as peças de corte na chapa e exporta o vetor. Abre em janela "
            "própria, pelo menu Ferramentas → Modo Corte.",
        ),
        TourStep(
            None, "Organizar encaixa sozinho",
            "O botão Organizar roda o encaixe (nesting) e aproveita o máximo "
            "da chapa. Ele roda em segundo plano, com barra de progresso — a "
            "janela continua respondendo.",
        ),
        TourStep(
            None, "Mover e girar na mão",
            "Não gostou do encaixe? Arraste as peças e gire com as setas. O "
            "que você ajustar na mão é respeitado na exportação.",
        ),
        TourStep(
            None, "Exportar o corte",
            "Sai em DXF (ou PDF de faca) para a sua máquina. Cada peça vira "
            "um contorno fechado, do jeito que a controladora espera.",
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
            "Recortar páginas ou imagem... corta as bordas em milímetros — "
            "serve para tirar marcas de corte, sangria ou moldura que vieram "
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
            "continua intacto — dá para desfazer o recorte quando quiser.",
        ),
    ]


def _exportar(window) -> list[TourStep]:
    return [
        TourStep(
            _alvo(window, "_ribbon"), "Centro de Exportação (Ctrl+E)",
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
            "Selecionou uma peça e apertou Ctrl+E? Dá para exportar só ela — "
            "útil para reposição sem refazer a chapa inteira.",
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
