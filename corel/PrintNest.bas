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
    Dim candidatos(3) As String
    candidatos(0) = PRINTNEST_EXE
    candidatos(1) = Environ$("LOCALAPPDATA") & "\Programs\PrintNest\PrintNest.exe"
    candidatos(2) = Environ$("ProgramFiles") & "\PrintNest\PrintNest.exe"
    candidatos(3) = Environ$("USERPROFILE") & "\Desktop\PrintNest\PrintNest.exe"
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
    Shell """" & exe & """ """ & arquivoPdf & """", vbNormalFocus
End Sub

' Botao principal: envia a PAGINA atual para o PrintNest.
Public Sub EnviarParaPrintNest()
    On Error GoTo erro
    Dim doc As Document
    Set doc = ActiveDocument
    If doc Is Nothing Then
        MsgBox "Abra um documento no CorelDRAW primeiro.", vbExclamation, "PrintNest"
        Exit Sub
    End If
    Dim pdf As String
    pdf = CaminhoTemp("printnest")
    ' PublishToPDF preserva os vetores (a linha de corte vai como vetor).
    doc.PublishToPDF pdf
    Disparar pdf
    Exit Sub
erro:
    MsgBox "Erro ao enviar para o PrintNest: " & Err.Description, vbCritical, "PrintNest"
End Sub

' Botao alternativo: envia APENAS a selecao (copia para um doc temporario,
' exporta e fecha). Sem selecao, envia a pagina.
Public Sub EnviarSelecaoParaPrintNest()
    On Error GoTo erro
    Dim src As Document
    Set src = ActiveDocument
    If src Is Nothing Then
        MsgBox "Abra um documento no CorelDRAW primeiro.", vbExclamation, "PrintNest"
        Exit Sub
    End If
    If src.Selection.Shapes.Count = 0 Then
        EnviarParaPrintNest   ' nada selecionado -> manda a pagina
        Exit Sub
    End If
    src.Selection.Copy
    Dim tmpDoc As Document
    Set tmpDoc = Application.CreateDocument
    tmpDoc.ActiveLayer.Paste
    Dim pdf As String
    pdf = CaminhoTemp("printnest_sel")
    tmpDoc.PublishToPDF pdf
    tmpDoc.Close
    Disparar pdf
    Exit Sub
erro:
    MsgBox "Erro ao enviar a selecao: " & Err.Description, vbCritical, "PrintNest"
End Sub
