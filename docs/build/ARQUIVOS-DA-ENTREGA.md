# Quais arquivos vão para o cliente

Referência rápida para não errar na hora de entregar. Versão 1.0.0.

---

## O arquivo que você entrega

**Um só:**

```
c:\projetos\Cutph\dist_installer\PrintNest-Setup-1.0.0.exe
```

É o **instalador**. Dentro dele já vai tudo: o programa, o LEIA-ME, o Tutor IA
em PDF, o plugin do CorelDRAW com as imagens do guia. O cliente dá dois cliques
e pronto.

É este arquivo que:
- sobe para a hospedagem
- vira o link do e-mail de entrega
- você copia no pendrive para testar em outro computador

**Não mande a pasta `PrintNest_Build` zipada.** Ela funciona, mas o cliente fica
sem atalho no menu Iniciar, sem entrada no Painel de Controle para desinstalar e
sem a tela dos termos de uso.

---

## As quatro cópias do programa (e por que existem)

Depois de um build, o mesmo programa aparece em quatro lugares. Só o primeiro
serve para entregar.

| Caminho | O que é | Entrega? |
|---|---|---|
| `dist_installer\PrintNest-Setup-1.0.0.exe` | **o instalador** | ✅ **sim** |
| `PrintNest_Build\PrintNest.exe` | o programa solto + LEIA-ME + Tutor IA + plugin. É a matéria-prima que o instalador empacota | ❌ não |
| `dist\PrintNest.exe` | saída crua do PyInstaller, antes de montar a pasta | ❌ não |
| `C:\Program Files\PrintNest\PrintNest.exe` | o que ficou instalado na sua máquina | ❌ não |

As três últimas têm conteúdo idêntico — é o mesmo programa em etapas diferentes
do processo.

---

## O que vai JUNTO do produto

Além do instalador, mande estes dois (no e-mail ou na página de download):

| Arquivo | Onde está | Para quê |
|---|---|---|
| `RELEASE-NOTES-1.0.0.md` | `docs\cliente\` | o que o programa faz, como instalar, como ativar |
| `PROBLEMAS-CONHECIDOS-1.0.0.md` | `docs\cliente\` | os 11 probleminhas conhecidos, cada um com a solução |

O segundo parece contraintuitivo — mas cliente avisado não abre chamado, ou abre
já sabendo o que fazer.

**No corpo do e-mail, obrigatoriamente:**

> Ao abrir o instalador, o Windows pode mostrar um aviso azul dizendo que
> "protegeu seu computador". Clique em **Mais informações** e depois em
> **Executar assim mesmo**. Esse aviso aparece em todo programa novo — o
> PrintNest é seguro.

Isso precisa estar no e-mail e na página, **não** só dentro do pacote: o cliente
encontra o aviso azul antes de conseguir abrir qualquer coisa.

---

## ⚠️ O que NUNCA pode sair da sua máquina

| Arquivo | Por quê |
|---|---|
| `tools\license_private_key.pem` | **é a chave que assina as licenças.** Quem tiver esse arquivo fabrica licença do PrintNest à vontade, de graça, para sempre |
| `tools\*.pem` em geral | mesma coisa |
| `tools\robot_config.json` | senha da conta de e-mail do robô de ativação |
| `tools\licenses_emitidas\` | dados de clientes e histórico de emissão |
| a pasta `app\` e o resto do projeto | é o código-fonte do produto que você vende |

**Nunca mande a pasta `tools` inteira, nunca mande o projeto inteiro.** O
instalador não contém nada disso — ele foi montado só com o que o cliente
precisa.

---

## Antes de enviar: conferir se é o arquivo certo

```powershell
Get-FileHash "c:\projetos\Cutph\dist_installer\PrintNest-Setup-1.0.0.exe" -Algorithm SHA256
```

O programa dentro dele tem de bater com o build validado:

```
2A49367B388BFF6AF056716718CC81548F6C884A1059C444DA00A0D5E76DA2DE
```

(esse hash é o do `PrintNest.exe`; para conferir o instalador em si, registre o
hash dele na primeira vez e compare nas próximas)

E confira a data em `PrintNest_Build\VERSAO.txt` — a última linha carimba a
data e hora reais da build.

---

## Guarde uma cópia fora da pasta do projeto

**Isto é importante.** Rodar `build.bat` **apaga e refaz** as pastas `dist` e
`PrintNest_Build`. Se você rodar o build de novo por qualquer motivo, o
instalador que foi validado deixa de existir com aquele conteúdo exato.

Copie o `PrintNest-Setup-1.0.0.exe` para uma pasta de arquivamento, um HD
externo ou a nuvem, com o hash anotado ao lado. É a sua prova de qual programa
está na mão de cada cliente.

---

## Testando em outro computador

1. Copie **só o `PrintNest-Setup-1.0.0.exe`** para o pendrive
2. Leve junto 2 ou 3 PDFs de arte real sua (não os de exemplo)
3. **Deixe o robô de licenças rodando na sua máquina**
   (`tools\iniciar_robo_licencas.bat`) — sem ele a ativação não responde e o
   teste trava logo no começo
4. Tenha um código de compra em mãos (`PNC-XXXX-XXXX`)

O passo a passo completo está em
[`docs/produto/TESTE-PC-NOVO.md`](../produto/TESTE-PC-NOVO.md).

---

## Gerando tudo de novo

Se um dia precisar refazer o pacote do zero:

```powershell
cd c:\projetos\Cutph
.\build.bat                                              # gera PrintNest_Build\
cd installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" printnest.iss   # gera o instalador
```

O instalador sai em `dist_installer\`. Depois disso, rode o
`PrintNest_Build\PrintNest.exe --selftest` para confirmar que o pacote está
íntegro antes de enviar para alguém.
