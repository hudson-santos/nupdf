// NuPDF.exe - launcher nativo do NuPDF.
//
// Dá ao NuPDF um .exe de verdade (compilado, com ícone e nome próprios) para
// os atalhos, o "Abrir com" do Explorer e o RemoteApp do Windows (que exige
// um executável real, não aceita "pythonw.exe main.py").
//
// Não reimplementa nada: chama "python\pythonw.exe main.py <args>" (Python embutido) na
// própria pasta de instalação, repassando os arquivos recebidos, e ESPERA o
// processo terminar (o RemoteApp considera a sessão "em uso" enquanto este
// processo estiver vivo).
//
// Compilado pelo instalar.ps1 (etapa 6) com o csc.exe do .NET Framework do
// Windows, junto com um .cs gerado na hora com AssemblyVersion = VERSAO de
// nupdf/versao.py. Para compilar manualmente (sem versão):
//
//   csc.exe /target:winexe /out:NuPDF.exe /win32icon:assets\nupdf.ico ^
//       /r:System.Windows.Forms.dll NuPDF.cs
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("NuPDF")]
[assembly: AssemblyDescription("NuPDF")]
[assembly: AssemblyProduct("NuPDF")]
[assembly: AssemblyCopyright("Nukt Ltda")]

internal static class NuPDFLauncher
{
    private static string Citar(string arg)
    {
        if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return arg;
        return "\"" + arg.Replace("\"", "\\\"") + "\"";
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string appDir = AppDomain.CurrentDomain.BaseDirectory;
        // Python embutido (C:\NuPDF\python); o venv é de instalações antigas
        string pythonw = Path.Combine(appDir, "python", "pythonw.exe");
        if (!File.Exists(pythonw))
            pythonw = Path.Combine(appDir, "venv", "Scripts", "pythonw.exe");
        string mainPy = Path.Combine(appDir, "main.py");

        if (!File.Exists(pythonw) || !File.Exists(mainPy))
        {
            MessageBox.Show(
                "Não encontrei \"" + pythonw + "\" e/ou \"" + mainPy + "\"." +
                Environment.NewLine + Environment.NewLine +
                "Execute o instalador do NuPDF novamente.",
                "NuPDF - erro ao iniciar",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }

        var linha = new StringBuilder("main.py");
        foreach (string a in args)
            linha.Append(' ').Append(Citar(Path.GetFullPath(a)));

        var info = new ProcessStartInfo
        {
            FileName = pythonw,
            Arguments = linha.ToString(),
            WorkingDirectory = appDir,
            UseShellExecute = false,
        };

        try
        {
            using (Process proc = Process.Start(info))
            {
                proc.WaitForExit();
                return proc.ExitCode;
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Não foi possível iniciar o NuPDF:" + Environment.NewLine + Environment.NewLine + ex.Message,
                "NuPDF - erro ao iniciar",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
    }
}
