# PrintNest Pro — Roteiro de Homologação (prompt de teste)

> COMO USAR: execute na ordem, marcando ✅/❌ em cada item. Qualquer ❌ vira
> chamado com: o que fez, o que esperava, o que aconteceu, print. O sistema só
> está "100%" quando TODAS as seções passarem. (Pode colar este documento numa
> IA e pedir: "me guie teste a teste e registre os resultados".)
>
> Preparação: PC "limpo" (sem Python), build mais recente, 1 PDF de várias
> páginas, 1 PDF com linha de corte vetorial (do Corel), 1 PNG com fundo
> transparente e vários desenhos separados (com um elemento pequeno ~4mm),
> 1 JPG de fundo branco, 1 imagem grande (>3000px) e 1 arquivo corrompido.

## 1. Instalação e ativação (fluxo do cliente pagante)
- [ ] Exe abre em PC limpo sem instalar nada além dele
- [ ] Sem licença: tela de Ativação BLOQUEIA (fechar = sair do programa)
- [ ] "Pedir minha chave por e-mail" abre e-mail pronto COM o ID da máquina
- [ ] Código de compra válido → chave chega por e-mail em ≤ 2 min (robô)
- [ ] Código já usado em OUTRO PC é recusado com orientação
- [ ] Mesmo PC pedindo de novo recebe a MESMA chave
- [ ] Chave colada → Ativar → libera; fechar e reabrir NÃO pede de novo
- [ ] Ajuda → Licença → Desativar: programa FECHA na hora; reabrir pede chave
- [ ] Copiar o exe + chave para outro PC NÃO funciona (node-locked)

## 2. Primeira experiência
- [ ] Programa abre MAXIMIZADO ocupando o monitor
- [ ] Tour de boas-vindas aparece sozinho na 1ª abertura; Próximo/Pular
      funcionam; passos iluminam as áreas certas; SEM emojis
- [ ] Tour não reaparece na 2ª abertura; Ajuda → Tour de boas-vindas repete
- [ ] Canvas vazio orienta: "Arraste seus arquivos para cá"
- [ ] Barra ✂ Faca NÃO aparece sem arquivos; aparece ao adicionar o primeiro

## 3. Importação
- [ ] PDF multipágina: cada página vira uma linha/peça; PNG, JPG e WEBP abrem
- [ ] Arrastar arquivos para o canvas funciona (além do botão)
- [ ] Mesmo arquivo importado 2x: SOMA quantidade (não duplica linha)
- [ ] Qtd altera cópias; arquivo corrompido dá erro amigável (não fecha o app)
- [ ] Arquivo movido/renomeado no disco: linha marca ⚠ e o app segue vivo
- [ ] "Cortar para (caixa do PDF)" alterna mídia/corte; "Recortar..." funciona

## 4. Geração de faca — tipos e ajustes
- [ ] GERAR FACA (botão azul / Shift+F5): faca vermelha aparece
- [ ] Automático: PNG transparente vira CONTORNO; JPG fundo branco vira RETÂNGULO
- [ ] Retângulo / Contorno justo / suave / simplificado: cada um responde
- [ ] Faca do cliente: PDF com vetor de corte usa EXATAMENTE aquela linha
- [ ] Offset +5mm afasta a faca; −2mm recua; Suavizar 0→5 arredonda visível
- [ ] Ajustes ▾: Raio dos cantos arredonda ATÉ retângulo; Nós Fino/Médio/Leve
      mudam a contagem sem entortar retas; cantos redondo/ponta/chanfro
- [ ] Curvas saem LISAS (sem facetas retas) no canvas com zoom forte

## 5. Escopo por arquivo (misturar corte reto + contorno)
- [ ] Sem seleção: etiqueta "Faca · documento"; ajuste vale para TODOS
- [ ] Peça selecionada: "Faca · este arquivo"; Tipo/Offset/Suavizar/Raio valem
      SÓ para o arquivo dela; os outros NÃO mudam
- [ ] Clicar no vazio volta o escopo para documento (etiqueta muda)
- [ ] Mudar Recorte/Giro GLOBAIS depois: afeta TAMBÉM o arquivo personalizado
- [ ] Aba Peça → "Usar padrão do documento" limpa os ajustes daquele arquivo

## 6. Comportamentos automáticos da faca
- [ ] Multi-desenho: PNG com N adesivos gera N facas; o elemento PEQUENO entra
- [ ] Espaçamento 0: quadrados colados viram GRADE de linhas contínuas
      (1 linha por borda comum); com 2mm voltam facas individuais
- [ ] Solda: sangria grande em desenhos vizinhos FUNDE os contornos numa linha
      externa única (nada de faca cruzando o adesivo do lado)
- [ ] Marcas de registro enquadram a peça INTEIRA no multi-desenho

## 7. Ferramenta Pontos (F10)
- [ ] Arrastar nó move; duplo clique no segmento ADICIONA; no nó REMOVE
- [ ] Cópias do mesmo arquivo herdam a edição; barra mostra "manual (Pontos)"
- [ ] Girar/redimensionar a peça depois: a faca manual acompanha
- [ ] "Voltar à faca automática" restaura; Ctrl+Z desfaz edição de nó

## 8. Organização e undo
- [ ] Arrastar peça com ímã de alinhamento; T/B/L/R/C/E alinham; Ctrl+G agrupa
- [ ] Ctrl+D duplica em cadeia; Ctrl+C/V cola; Del exclui; Ctrl+L reorganiza
- [ ] CTRL+Z desfaz UM passo por vez (mover → offset → suavizar = 3 undos
      separados); segurar a setinha de um campo = 1 undo só; Ctrl+Y refaz
- [ ] Remover arquivo da biblioteca; remover o ÚLTIMO limpa tudo e o canvas
      volta a orientar (barra Faca some)

## 9. Chapa e canvas
- [ ] Largura/Altura da chapa aplicam; Altura 0 = comprimento livre
- [ ] Ajustar chapa ao conteúdo (Ctrl+Shift+F): chapa abraça o arranjo;
      exportação SEM branco em volta; Ctrl+Z desfaz
- [ ] Zoom da RODA vai onde o mouse aponta (teste nos 4 cantos)
- [ ] Pan livre (botão do meio / H) além das bordas; F4 reenquadra
- [ ] Réguas acompanham zoom/pan; guias arrastáveis das réguas; mm ↔ cm
- [ ] Modos de exibição: Impressão / Corte / Tela dividida — idênticos ao
      que exporta; barrinha flutuante arrasta e colapsa no olho
- [ ] Minimizar e restaurar com zoom "perdido": vista se recupera sozinha

## 10. Exportação (a prova final de cada job)
- [ ] PDF de impressão: mede uma peça no PDF = medida do app (régua!)
- [ ] DXF abre no CorelDRAW SEM espelhar, unidade mm correta, layer CUT;
      curvas como spline lisa; grade fundida OK; abre no software da MÁQUINA
- [ ] Faca em PDF: linhas idênticas ao preview; bolinhas de registro pretas
- [ ] Impressão×Corte ALINHAM (sobreponha os dois PDFs): marcas casam 1:1
- [ ] PNG/JPEG no DPI escolhido; exportar chapas específicas ("1,3"); Ctrl+E
      exporta só a seleção
- [ ] Exportar Faca SEM ter gerado faca: recusa com aviso (não gera vazio)
- [ ] Pasta sem permissão/inexistente: erro amigável, app vivo
- [ ] Durante exportação grande: cursor de espera (app não "parece travado")

## 11. Projetos e abas
- [ ] Ctrl+S salva .printnest; fechar e reabrir restaura: arquivos, qtds,
      parâmetros, AJUSTES POR ARQUIVO e FACAS EDITADAS A MÃO
- [ ] Último projeto reabre sozinho ao iniciar; abrir projeto INTOCADO e
      fechar o app NÃO pergunta "salvar alterações?"
- [ ] Com alterações: Novo/Abrir/Fechar app/Fechar aba perguntam
      Salvar/Descartar/Cancelar (Cancelar aborta MESMO)
- [ ] Abas: "+" cria trabalho paralelo; cada aba mantém seus arquivos/ajustes;
      clipboard NÃO atravessa abas

## 12. Temas e aparência
- [ ] Opções → Aparência → Escuro/Midnight/Carbon/Claro/Automático: TUDO muda
      junto (tabela, painéis, checkbox, tooltips, logo inverte) — caçar
      qualquer texto ilegível ou área branca perdida no escuro
- [ ] Personalizar Interface: acento recolore botões/seleção NA HORA; presets;
      cores individuais; Cancelar volta como estava; exportar/importar JSON
- [ ] Tema persiste ao fechar/reabrir; no claro, botões DESABILITADOS ficam
      acinzentados

## 13. Plugin CorelDRAW
- [ ] instalar_plugin_corel.bat instala (com Corel fechado dá orientação)
- [ ] Botão criado na barra; SEM caminho configurado à mão: abrir o PrintNest
      1x basta ("se anuncia")
- [ ] Com seleção envia SÓ a seleção; sem seleção envia a página
- [ ] PrintNest já aberto: arquivo entra na sessão atual (não abre 2º programa)
- [ ] Faca do cliente do PDF do Corel sai EXATA

## 14. Responsividade e estresse
- [ ] Notebook 1366×768 e escala 125%/150%: NADA cortado (barra Faca, campos,
      diálogos, número do Suavizar); Modo Compacto utilizável
- [ ] 200+ cópias de uma peça: gerar/mover/zoom sem travar; exportar OK
- [ ] Imagem >3000px importa e gera contorno em segundos
- [ ] Abrir/fechar o programa 5x seguidas: sem erro, sem janela fantasma

## 15. Extras do pacote
- [ ] "Tutor IA - PrintNest.pdf" está na pasta; jogar numa IA e perguntar
      "como faço corte rente?" → resposta correta com os passos do app
- [ ] VERSAO.txt com data da build; título mostra v3.0.0

## Critério de saída
100% = todas as caixas ✅ em DOIS ambientes (PC de desenvolvimento e PC limpo)
+ 1 job REAL de gráfica impresso e cortado na máquina com registro casando.
