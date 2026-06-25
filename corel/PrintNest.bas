Attribute VB_Name = "PrintNest"
' ==========================================================================
'  PrintNest - Integracao CorelDRAW  (estilo RDWorks)
'  Desenhe no CorelDRAW, clique no botao e o arquivo cai no PrintNest.
'  A linha de corte desenhada como VETOR vai no PDF e o PrintNest a usa
'  como "Faca do cliente".
'
'  Instalacao: veja corel/README.md (Alt+F11 -> importar este arquivo ->
'  criar um botao na barra apontando para "EnviarParaPrintNest").
' ==========================================================================
Option Explicit

' ---- AJUSTE AQUI o caminho do PrintNest instalado ----
Private Const PRINTNEST_EXE As String = "C:\Program Files\PrintNest\PrintNest.exe"

' Localiza o executavel do PrintNest (tenta o caminho configurado e alguns
' lugares comuns). Retorna "" se nao achar.
Private Function PrintNestExe() As String
    Dim candidatos(4) As String
    candidatos(0) = PRINTNEST_EXE
    candidatos(1) = Environ$("LOCALAPPDATA") & "\Programs\PrintNest\PrintNest.exe"
    candidatos(2) = Environ$("ProgramFiles") & "\PrintNest\PrintNest.exe"
    candidatos(3) = Environ$("USERPROFILE") & "\Desktop\PrintNest\PrintNest.exe"
    ' fallback de desenvolvimento (roda o PrintNest direto do codigo)
    candidatos(4) = "c:\projetos\Cutph\corel\run_printnest_dev.bat"
    Dim i As Integer
    For i = 0 To UBound(candidatos)
        If Len(candidatos(i)) > 0 Then
            If Dir(candidatos(i)) <> "" Then
                PrintNestExe = candidatos(i)
                Exit Function
            End If
        End If
    Next i
    PrintNestExe = ""
End Function

Private Function CaminhoTemp(prefixo As String) As String
    CaminhoTemp = Environ$("TEMP") & "\" & prefixo & "_" & _
                  Format(Now, "yyyymmdd_hhnnss") & ".pdf"
End Function

Private Sub Disparar(arquivoPdf As String)
    Dim exe As String
    exe = PrintNestExe()
    If exe = "" Then
        MsgBox "PrintNest nao encontrado." & vbCrLf & _
               "Abra esta macro (Alt+F11) e ajuste a constante PRINTNEST_EXE " & _
               "com o caminho do PrintNest.exe.", vbExclamation, "PrintNest"
        Exit Sub
    End If
    ' aspas para suportar espacos nos caminhos. O PrintNest e instancia unica:
    ' se ja estiver aberto, o arquivo entra na sessao atual.
    ' .bat precisa ser disparado via "cmd /c" (Shell nao roda .bat direto).
    If LCase$(Right$(exe, 4)) = ".bat" Then
        Shell "cmd /c """ & exe & """ """ & arquivoPdf & """", vbHide
    Else
        Shell """" & exe & """ """ & arquivoPdf & """", vbNormalFocus
    End If
End Sub

' ---- logica interna ----
Private Sub EnviarPagina()
    Dim doc As Document
    Set doc = ActiveDocument
    Dim pdf As String
    pdf = CaminhoTemp("printnest")
    ' PublishToPDF preserva os VETORES (a linha de corte vai como vetor).
    doc.PublishToPDF pdf
    Disparar pdf
End Sub

Private Sub EnviarSelecao()
    Dim src As Document
    Set src = ActiveDocument
    src.Selection.Copy
    Dim tmpDoc As Document
    Set tmpDoc = Application.CreateDocument
    tmpDoc.ActiveLayer.Paste
    Dim pdf As String
    pdf = CaminhoTemp("printnest_sel")
    tmpDoc.PublishToPDF pdf
    tmpDoc.Close
    Disparar pdf
End Sub

' ===== BOTAO PRINCIPAL (inteligente) =====
' Se houver SELECAO, envia so a selecao (recortado). Senao, envia a pagina.
' Um clique so faz a coisa certa -> mais facil para o operador.
Public Sub EnviarParaPrintNest()
    On Error GoTo erro
    If ActiveDocument Is Nothing Then
        MsgBox "Abra um documento no CorelDRAW primeiro.", vbExclamation, "PrintNest"
        Exit Sub
    End If
    If ActiveDocument.Selection.Shapes.Count > 0 Then
        EnviarSelecao
    Else
        EnviarPagina
    End If
    Exit Sub
erro:
    MsgBox "Erro ao enviar para o PrintNest: " & Err.Description, vbCritical, "PrintNest"
End Sub

' Botoes explicitos (opcionais), caso queira forcar um modo:
Public Sub EnviarSelecaoParaPrintNest()
    On Error GoTo erro
    If ActiveDocument Is Nothing Then Exit Sub
    If ActiveDocument.Selection.Shapes.Count = 0 Then
        EnviarPagina
    Else
        EnviarSelecao
    End If
    Exit Sub
erro:
    MsgBox "Erro ao enviar a selecao: " & Err.Description, vbCritical, "PrintNest"
End Sub

Public Sub EnviarPaginaParaPrintNest()
    On Error GoTo erro
    If ActiveDocument Is Nothing Then Exit Sub
    EnviarPagina
    Exit Sub
erro:
    MsgBox "Erro ao enviar a pagina: " & Err.Description, vbCritical, "PrintNest"
End Sub

' Botao "Abrir PrintNest": so abre o programa (ou traz a janela ja aberta para
' a frente, por causa da instancia unica). Nao envia nenhum arquivo.
Public Sub AbrirPrintNest()
    On Error GoTo erro
    Dim exe As String
    exe = PrintNestExe()
    If exe = "" Then
        MsgBox "PrintNest nao encontrado." & vbCrLf & _
               "Abra esta macro (Alt+F11) e ajuste a constante PRINTNEST_EXE.", _
               vbExclamation, "PrintNest"
        Exit Sub
    End If
    If LCase$(Right$(exe, 4)) = ".bat" Then
        Shell "cmd /c """ & exe & """", vbHide
    Else
        Shell """" & exe & """", vbNormalFocus
    End If
    Exit Sub
erro:
    MsgBox "Erro ao abrir o PrintNest: " & Err.Description, vbCritical, "PrintNest"
End Sub
