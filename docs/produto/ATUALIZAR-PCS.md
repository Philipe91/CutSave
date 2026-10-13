# Atualizar os PCs que já usam o PrintNest

Roteiro de campo. Versão atual: **1.2.2**.

Atualizar é **instalar por cima**. Não desinstale a versão antiga — o
instalador reconhece a instalação existente pelo `AppId` e troca só o
programa. Licença e configurações ficam onde estão.

---

## Antes de sair da mesa

| # | O quê | Feito |
|---|---|---|
| 1 | Copiar `dist_installer\PrintNest-Setup-1.2.2.exe` para pendrive ou nuvem | ☐ |
| 2 | Guardar **uma cópia do instalador fora da pasta do projeto** (HD externo, nuvem). Rodar `build.bat` de novo apaga e refaz `dist_installer\` | ☐ |
| 3 | Conferir o SHA-256 do arquivo que você copiou (tabela em `docs/build/ARQUIVOS-DA-ENTREGA.md`) | ☐ |
| 4 | Subir o robô de licenças (`tools\iniciar_robo_licencas.bat`) e deixar rodando | ☐ |

O item 4 é por precaução: a atualização **não** deve pedir ativação de novo.
Mas se algum PC pedir, sem o robô no ar você fica parado na frente da máquina
do cliente sem ter o que fazer.

---

## O PRIMEIRO PC é o teste. Trate como tal.

Escolha o PC menos crítico — de preferência o seu, ou um que não esteja no
meio de um trabalho. Ele decide se os outros podem ser atualizados.

| # | Passo | OK? |
|---|---|---|
| 1 | Anotar antes: a versão atual (Ajuda → Sobre) e se o PC está **ativado** | ☐ |
| 2 | **Fechar o PrintNest** (aberto, o instalador não consegue trocar o arquivo) | ☐ |
| 3 | Rodar o instalador. SmartScreen pode avisar: *Mais informações* → *Executar assim mesmo* | ☐ |
| 4 | **Não** marcar "executar agora" ao final. Espere alguns segundos e abra pelo atalho — o antivírus varre o executável recém-gravado, e abrir naquele instante já causou "Failed to load Python DLL" | ☐ |
| 5 | O app abre **já ativado**. Não pode pedir código de novo | ☐ |
| 6 | Ajuda → Sobre mostra **1.2.2** | ☐ |
| 7 | As configurações continuam como estavam: DPI de exportação, tipo de marca de registro, unidade (cm/mm) | ☐ |
| 8 | Abrir um projeto `.printnest` antigo: o arranjo volta como estava | ☐ |
| 9 | Exportar um PDF de impressão de teste — só para ver o fluxo inteiro funcionando | ☐ |

### Se o passo 5 falhar (pediu ativação de novo)

**PARE. Não atualize mais nenhum PC.** O cliente fica sem conseguir trabalhar.

Reativar é possível com o robô no ar, mas o problema precisa ser entendido
antes de espalhar. Me chame com: o que apareceu na tela, e se o arquivo
`%APPDATA%\PrintNest\license.key` ainda existe naquele PC.

---

## Nos demais PCs

Passos 2 a 6 do quadro acima. Os passos 7 a 9 valem no primeiro PC de cada
gráfica, não em todos.

### Registro

Anote — se um PC ficar para trás, é isso que vai te dizer qual:

| PC / Máquina | Data | Versão antes | Abriu ativado? | OK |
|---|---|---|---|---|
| PC do Philipe (dev) — **gate** | 04/09/2026 | 1.1.3 | sim, licença com hash idêntico ao de antes | ✅ |
| PC do Philipe (dev) — **gate 1.2.1** | 11/09/2026 | 1.2.0 | sim, license.key com hash idêntico | ✅ |
| | | | | |

---

## Depois de atualizar: o teste que importa

### Na 1.2.2 — tela pequena e faca

- Selecione uma peça: os campos da "Faca deste arquivo" não podem aparecer
  uns por cima dos outros (o painel rola).
- Diminua a janela: a barra de cima não ganha rolagem lateral; o que não cabe
  aparece no botão **»**.
- Gere a faca de uma imagem PNG/JPG: o contorno segue a arte.

### Na 1.2.1 — exportação em imagem

Em pelo menos um PC, com uma arte **CMYK** do cliente e uma chapa cheia (dezenas
de cópias): **Centro de Exportação → JPEG 300 DPI CMYK**. Tem de aparecer a
janela "Exportando imagem" com etapa, barra, tempo decorrido e dicas; a barra
de título **não** pode marcar "Não está respondendo"; a chapa sai em menos de
um minuto (na 1.2.0 passava de 10). Clicar **Cancelar** numa segunda tentativa
fecha em poucos segundos e não deixa arquivo na pasta.

### Na 1.2.0 — cor

A 1.2.0 corrige um defeito de **cor**. Ele não aparece nos arquivos de
exemplo, que são RGB — só numa arte **CMYK** de verdade.

Em pelo menos um PC, com uma arte CMYK do cliente:

1. Importar a arte, montar a chapa, exportar em **PDF**
2. Abrir no Acrobat → Produção de impressão → **Visualização de saída**
3. As separações têm de aparecer em **CMYK**, não em RGB
4. Isolando o canal **K**: as marcas de registro aparecem só nele

**Exporte em PDF, não em imagem.** A exportação em imagem passa por uma
rasterização em RGB, então o CMYK dela é conversão — tinta pura não volta
igual. Julgar a correção pela imagem leva a conclusão errada. Isso está
explicado no `RELEASE-NOTES-1.2.0.md` que vai junto para o cliente.

---

## Avisar os PCs que você não vai visitar

O app consulta um manifesto e avisa sozinho quando há versão nova (o cliente
instala na mão). Para acionar, publique o `versao.json` com:

```json
{
  "versao": "1.2.1",
  "url": "https://seu-site/downloads/PrintNest-Setup-1.2.1.exe",
  "notas": "Exportacao em imagem de arte CMYK voltou a ser rapida, com janela de acompanhamento e Cancelar."
}
```

Detalhes em [`ATUALIZACAO.md`](ATUALIZACAO.md).

---

## O que NÃO fazer

- **Não desinstalar antes de instalar a nova.** Desinstalar preserva a licença
  de propósito, mas é passo desnecessário e uma chance a mais de erro.
- **Não atualizar no meio de um trabalho em produção.** Faça no começo ou no
  fim do expediente.
- **Não mandar a pasta `PrintNest_Build` zipada** no lugar do instalador: o
  cliente fica sem atalho, sem entrada no Painel de Controle e sem os termos
  de uso.
- **Nunca copiar a pasta `tools`** para lugar nenhum: ela tem a chave que
  assina as licenças e a senha do robô.
