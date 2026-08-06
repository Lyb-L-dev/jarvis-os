Option Explicit

Dim shell, environment, text, rate, volume, outputPath, mode, preferredVoice
Dim probe, voices, index, success, errorText

Set shell = CreateObject("WScript.Shell")
Set environment = shell.Environment("Process")

text = environment("JARVIS_TTS_TEXT")
rate = CInt(environment("JARVIS_TTS_RATE"))
volume = CInt(environment("JARVIS_TTS_VOLUME"))
outputPath = environment("JARVIS_TTS_OUTPUT")
mode = LCase(WScript.Arguments.Item(0))
preferredVoice = LCase(environment("JARVIS_TTS_VOICE"))

Set probe = CreateObject("SAPI.SpVoice")
Set voices = probe.GetVoices()
success = False
errorText = ""

If preferredVoice <> "" And preferredVoice <> "auto_zh" Then
    For index = 0 To voices.Count - 1
        If InStr(1, LCase(voices.Item(index).GetDescription()), preferredVoice, 1) > 0 Then
            If TryVoice(voices.Item(index), mode, text, rate, volume, outputPath, errorText) Then
                success = True
                Exit For
            End If
        End If
    Next
End If

If Not success Then
    For index = 0 To voices.Count - 1
        If InStr(1, LCase(voices.Item(index).GetAttribute("Language")), "804", 1) > 0 Then
            If TryVoice(voices.Item(index), mode, text, rate, volume, outputPath, errorText) Then
                success = True
                Exit For
            End If
        End If
    Next
End If

If Not success Then
    For index = 0 To voices.Count - 1
        If TryVoice(voices.Item(index), mode, text, rate, volume, outputPath, errorText) Then
            success = True
            Exit For
        End If
    Next
End If

If success Then
    WScript.Quit 0
End If

WScript.Echo "No installed Windows voice could synthesize speech. " & errorText
WScript.Quit 1


Function TryVoice(token, selectedMode, speechText, speechRate, speechVolume, wavePath, ByRef lastError)
    Dim voice, stream, errorNumber, errorDescription, fileSystem

    On Error Resume Next
    Err.Clear
    Set voice = CreateObject("SAPI.SpVoice")
    Set voice.Voice = token
    voice.Rate = speechRate
    voice.Volume = speechVolume

    If selectedMode = "wave" Then
        Set stream = CreateObject("SAPI.SpFileStream")
        stream.Open wavePath, 3, False
        Set voice.AudioOutputStream = stream
    End If

    voice.Speak speechText
    errorNumber = Err.Number
    errorDescription = Err.Description
    Err.Clear

    If selectedMode = "wave" And Not stream Is Nothing Then
        stream.Close
    End If

    If errorNumber = 0 Then
        TryVoice = True
    Else
        lastError = token.GetDescription() & ": " & errorDescription
        If selectedMode = "wave" Then
            Set fileSystem = CreateObject("Scripting.FileSystemObject")
            If fileSystem.FileExists(wavePath) Then
                fileSystem.DeleteFile wavePath, True
            End If
        End If
        TryVoice = False
    End If
    On Error GoTo 0
End Function
