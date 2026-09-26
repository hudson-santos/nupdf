<#
    Grava o AppUserModelID (System.AppUserModel.ID) num atalho (.lnk).

    Por que isso existe: main.py chama SetCurrentProcessExplicitAppUserModelID
    ("NuPDF.App") logo na inicialização - a partir do momento em que um
    processo declara um AppUserModelID explícito, o Windows passa a resolver
    "Fixar na barra de tarefas" (a partir do ícone da janela ENQUANTO o NuPDF
    está rodando) só correlacionando esse AppID com o de algum atalho - deixa
    de tentar casar pelo caminho do executável (pythonw.exe + argumentos).

    Sem o mesmo AppID gravado no atalho, essa correlação falha mesmo com um
    atalho no Menu Iniciar existindo e com IconLocation certo (foi o que
    aconteceu: o fix anterior - criar o atalho no Menu Iniciar - resolveu o
    caso de fixar A PARTIR do atalho, mas não o caso de fixar a partir do
    ícone da janela rodando) - o Windows não encontra nenhum atalho com o
    AppID "NuPDF.App" e cai de volta no ícone embutido no pythonw.exe (o
    "cobrinha" do Python).

    WScript.Shell (usado no Instalador.bat para criar os atalhos) não expõe
    essa propriedade - só dá para gravar via IPropertyStore (COM), daí este
    script à parte em vez de mais uma linha de PowerShell -Command inline.

    `-Pasta` recebe um nome de pasta especial do .NET
    ([Environment]::GetFolderPath), não um caminho pronto - os mesmos
    identificadores já usados no Instalador.bat para criar os atalhos
    (Desktop/Startup/Programs). Resolver aqui, do mesmo jeito, evita
    divergir do caminho real caso a pasta esteja redirecionada (ex.:
    Área de Trabalho movida para o OneDrive) - um caminho fixo do tipo
    "%USERPROFILE%\Desktop" poderia apontar para uma pasta sem o atalho.

    Um atalho por chamada (não uma lista) de propósito: chamado via
    "powershell -File" a partir do Instalador.bat (cmd.exe), onde os
    argumentos chegam como tokens crus de linha de comando, não como
    sintaxe do PowerShell - um "-Pastas 'a','b','c'" não vira array
    nesse cenário (só o primeiro token se liga ao parâmetro, os
    seguintes ficam soltos, sem parâmetro posicional pra receber).
    Mesmo padrão dos 3 blocos quase idênticos já usados no Instalador.bat
    para criar os atalhos, um por vez.

    Uso:
        powershell -File definir_appid_atalho.ps1 -AppId "NuPDF.App" -Pasta "Desktop"

    Melhor esforço: uma falha (ex.: SHGetPropertyStoreFromParsingName sem
    suporte numa versão antiga do Windows) é avisada e ignorada, sem
    interromper o instalador.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$AppId,

    [Parameter(Mandatory = $true)]
    [string]$Pasta
)

Add-Type @'
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
public struct PROPERTYKEY {
    public Guid fmtid;
    public int pid;
    public PROPERTYKEY(string fmtid, int pid) {
        this.fmtid = new Guid(fmtid);
        this.pid = pid;
    }
}

[StructLayout(LayoutKind.Explicit)]
public struct PROPVARIANT {
    [FieldOffset(0)] public short vt;
    [FieldOffset(8)] public IntPtr pointerValue;
}

[ComImport]
[Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
    int GetCount(out uint propertyCount);
    int GetAt(uint propertyIndex, out PROPERTYKEY key);
    int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
    int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
    int Commit();
}

public static class AtalhoAppId {
    private const int GPS_READWRITE = 0x2;
    private const short VT_LPWSTR = 31;

    [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
    private static extern void SHGetPropertyStoreFromParsingName(
        string pszPath, IntPtr pbc, int flags, ref Guid riid,
        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore propertyStore);

    [DllImport("ole32.dll", PreserveSig = false)]
    private static extern void PropVariantClear(ref PROPVARIANT pvar);

    public static void Definir(string caminhoAtalho, string appId) {
        Guid iid = typeof(IPropertyStore).GUID;
        IPropertyStore propertyStore;
        SHGetPropertyStoreFromParsingName(caminhoAtalho, IntPtr.Zero, GPS_READWRITE, ref iid, out propertyStore);

        PROPERTYKEY pkeyAppUserModelId = new PROPERTYKEY("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3", 5);
        PROPVARIANT pv = new PROPVARIANT();
        pv.vt = VT_LPWSTR;
        pv.pointerValue = Marshal.StringToCoTaskMemUni(appId);

        try {
            propertyStore.SetValue(ref pkeyAppUserModelId, ref pv);
            propertyStore.Commit();
        } finally {
            PropVariantClear(ref pv);
            Marshal.ReleaseComObject(propertyStore);
        }
    }
}
'@

$atalho = Join-Path ([Environment]::GetFolderPath($Pasta)) "NuPDF.lnk"
try {
    [AtalhoAppId]::Definir($atalho, $AppId)
    Write-Host "      AppUserModelID gravado em $atalho"
} catch {
    Write-Host "      [AVISO] Não foi possível gravar o AppUserModelID em $atalho`: $_"
}
