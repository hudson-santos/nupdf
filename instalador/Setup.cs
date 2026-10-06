// Instalador.exe - janela de instalação do NuPDF (no estilo da do Chrome/Gemini).
//
// O motor continua sendo o Inno Setup (Instalador.iss -> InstaladorInno.exe), que
// vai embutido aqui como recurso e roda em modo /VERYSILENT, sem o assistente.
// Esta janela só mostra o progresso: o [Code] do Instalador.iss grava cada etapa
// no arquivo indicado pela variável de ambiente NUPDF_PROGRESSO, no formato
// "inicio|fim|texto" (faixa da barra, em %) ou "erro|mensagem".
//
// Modos:
//   (sem parâmetros) ou /SILENT  -> esta janela (instalação manual e a atualização
//                                   automática do NuPDF, que passa /SILENT); no fim
//                                   abre o NuPDF.
//   /VERYSILENT                  -> sem janela nenhuma: repassa os parâmetros ao Inno
//                                   e devolve o código de saída dele (Microsoft Store,
//                                   implantações automatizadas).
//
// Compilado por instalador\compilar_instalador.ps1 (local e no GitHub Actions).
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Text;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Instalador do NuPDF")]
[assembly: AssemblyDescription("Instalador do NuPDF")]
[assembly: AssemblyProduct("NuPDF")]
[assembly: AssemblyCompany("Nukt Ltda")]
[assembly: AssemblyCopyright("Nukt Ltda")]

internal static class Programa
{
    internal const string PastaApp = @"C:\NuPDF";

    [DllImport("user32.dll")]
    private static extern bool SetProcessDPIAware();

    [STAThread]
    private static int Main(string[] args)
    {
        bool muitoSilencioso = args.Any(a => string.Equals(a, "/VERYSILENT", StringComparison.OrdinalIgnoreCase));
        if (muitoSilencioso)
            return Motor.Executar(string.Join(" ", args.Select(Citar)), null);

        try { SetProcessDPIAware(); } catch { }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        var janela = new JanelaInstalacao(File.Exists(Path.Combine(PastaApp, "NuPDF.exe")));
        Application.Run(janela);
        return janela.CodigoSaida;
    }

    internal static string Citar(string arg)
    {
        if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return arg;
        return "\"" + arg.Replace("\"", "\\\"") + "\"";
    }
}

// Extrai o InstaladorInno.exe embutido para uma pasta temporária e o executa.
internal static class Motor
{
    internal static int Executar(string parametros, string arquivoProgresso)
    {
        string pasta = Path.Combine(Path.GetTempPath(), "NuPDF-Instalador-" + Process.GetCurrentProcess().Id);
        Directory.CreateDirectory(pasta);
        string exe = Path.Combine(pasta, "InstaladorInno.exe");
        try
        {
            using (Stream origem = Assembly.GetExecutingAssembly().GetManifestResourceStream("NuPDF.Motor.exe"))
            using (FileStream destino = File.Create(exe))
                origem.CopyTo(destino);

            var info = new ProcessStartInfo(exe, parametros) { UseShellExecute = false, WorkingDirectory = pasta };
            if (arquivoProgresso != null)
                info.EnvironmentVariables["NUPDF_PROGRESSO"] = arquivoProgresso;
            using (Process p = Process.Start(info))
            {
                p.WaitForExit();
                return p.ExitCode;
            }
        }
        finally
        {
            try { Directory.Delete(pasta, true); } catch { }
        }
    }
}

internal sealed class JanelaInstalacao : Form
{
    // mesmas cores do tema claro do NuPDF (nupdf/tema.py)
    private static readonly Color Fundo = Color.White;
    private static readonly Color Borda = Color.FromArgb(0xDD, 0xDE, 0xE2);
    private static readonly Color Texto = Color.FromArgb(0x1F, 0x20, 0x23);
    private static readonly Color Texto2 = Color.FromArgb(0x6B, 0x6F, 0x76);
    private static readonly Color Destaque = Color.FromArgb(0xE5, 0x48, 0x4D);
    private static readonly Color Trilho = Color.FromArgb(0xEC, 0xED, 0xF0);
    private static readonly Color Hover = Color.FromArgb(0xF1, 0xF2, 0xF4);
    private static readonly Color Cinza = Color.FromArgb(0x4B, 0x4D, 0x53);

    private enum Estado { Instalando, Concluido, Erro }

    private readonly bool _atualizacao;
    private readonly float _s;  // escala de DPI
    private readonly Image _logo;
    private readonly string _arquivoProgresso;
    private readonly System.Windows.Forms.Timer _timer = new System.Windows.Forms.Timer { Interval = 30 };
    private readonly Stopwatch _relogio = new Stopwatch();

    private Estado _estado = Estado.Instalando;
    private string _status = "Preparando a instalação";
    private string _erro = "";
    private double _inicio, _fim = 4, _exibido;
    private double _inicioEtapa;  // segundos (_relogio) em que a etapa atual começou
    private string _ultimaLinha = "";
    private Thread _thread;
    private bool _escondida;
    private string _hover = "";

    internal int CodigoSaida = 1;

    public JanelaInstalacao(bool atualizacao)
    {
        _atualizacao = atualizacao;
        using (Graphics g = CreateGraphics())
            _s = g.DpiX / 96f;
        _arquivoProgresso = Path.Combine(Path.GetTempPath(), "nupdf_progresso_" + Process.GetCurrentProcess().Id + ".txt");
        using (Stream st = Assembly.GetExecutingAssembly().GetManifestResourceStream("NuPDF.Logo.png"))
            _logo = Image.FromStream(st);

        Text = atualizacao ? "Atualizando NuPDF" : "Instalador do NuPDF";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;  // centralizada em OnLoad
        ClientSize = new Size(E(460), E(280));
        BackColor = Fundo;
        DoubleBuffered = true;
        KeyPreview = true;

        _timer.Tick += (o, e) => Animar();
    }

    private int E(float v) { return (int)Math.Round(v * _s); }

    // ------------------------------------------------------------------ janela
    protected override CreateParams CreateParams
    {
        get
        {
            const int CS_DROPSHADOW = 0x20000, WS_MINIMIZEBOX = 0x20000, WS_SYSMENU = 0x80000;
            CreateParams cp = base.CreateParams;
            cp.Style |= WS_MINIMIZEBOX | WS_SYSMENU;  // minimizar/fechar pela barra de tarefas
            if (!Windows11()) cp.ClassStyle |= CS_DROPSHADOW;
            return cp;
        }
    }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int valor, int tamanho);

    [StructLayout(LayoutKind.Sequential)]
    private struct Margens { public int Esq, Dir, Topo, Base; }

    [DllImport("dwmapi.dll")]
    private static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref Margens m);

    [DllImport("user32.dll")]
    private static extern bool ReleaseCapture();

    [DllImport("user32.dll")]
    private static extern IntPtr SendMessage(IntPtr hwnd, int msg, IntPtr w, IntPtr l);

    private static bool Windows11()
    {
        return Environment.OSVersion.Version.Major >= 10 && Environment.OSVersion.Version.Build >= 22000;
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        if (Windows11())
        {
            try
            {
                int arredondado = 2;  // DWMWA_WINDOW_CORNER_PREFERENCE = DWMWCP_ROUND
                DwmSetWindowAttribute(Handle, 33, ref arredondado, sizeof(int));
                var m = new Margens { Esq = 1, Dir = 1, Topo = 1, Base = 1 };  // sombra do Windows
                DwmExtendFrameIntoClientArea(Handle, ref m);
            }
            catch { }
        }
    }

    protected override void OnLoad(EventArgs e)
    {
        base.OnLoad(e);
        Centralizar();
    }

    // No centro da área de trabalho do monitor onde está o mouse (onde o usuário
    // abriu o instalador). O CenterScreen do WinForms usa o tamanho de antes da
    // escala de DPI e pode deixar a janela deslocada.
    private void Centralizar()
    {
        Rectangle area = Screen.FromPoint(Cursor.Position).WorkingArea;
        Location = new Point(area.Left + (area.Width - Width) / 2, area.Top + (area.Height - Height) / 2);
    }

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        Iniciar();
    }

    // ------------------------------------------------------------------ instalação
    private void Iniciar()
    {
        _estado = Estado.Instalando;
        _status = "Preparando a instalação";
        _erro = "";
        _inicio = 0; _fim = 4; _exibido = 0; _ultimaLinha = "";
        _relogio.Restart();
        _inicioEtapa = 0;
        try { File.Delete(_arquivoProgresso); } catch { }
        _timer.Start();
        Invalidate();

        _thread = new Thread(() =>
        {
            int codigo;
            try
            {
                codigo = Motor.Executar("/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-", _arquivoProgresso);
            }
            catch (Exception ex)
            {
                codigo = -1;
                _erro = ex.Message;
            }
            BeginInvoke(new Action(() => Terminou(codigo)));
        }) { IsBackground = true };
        _thread.Start();
    }

    private void LerProgresso()
    {
        string linha;
        try
        {
            if (!File.Exists(_arquivoProgresso)) return;
            // compartilhado para escrita: ler não pode impedir o Inno de gravar a próxima etapa
            using (var fs = new FileStream(_arquivoProgresso, FileMode.Open, FileAccess.Read,
                                           FileShare.ReadWrite | FileShare.Delete))
            using (var leitor = new StreamReader(fs, System.Text.Encoding.Default, true))
                linha = leitor.ReadToEnd().Trim();
        }
        catch { return; }  // o Inno pode estar gravando neste instante
        if (linha == _ultimaLinha || linha.Length == 0) return;
        _ultimaLinha = linha;
        string[] p = linha.Split(new[] { '|' }, 3);
        if (p[0] == "erro")
        {
            _erro = p.Length > 1 ? p[1] : "";
            return;
        }
        double ini, fim;
        if (p.Length == 3 && double.TryParse(p[0], out ini) && double.TryParse(p[1], out fim))
        {
            _inicio = Math.Max(ini, _exibido);
            _fim = fim;
            _status = p[2];
            _inicioEtapa = _relogio.Elapsed.TotalSeconds;
        }
    }

    private void Animar()
    {
        if (_estado == Estado.Instalando)
        {
            LerProgresso();
            // dentro da etapa a barra avança sozinha, cada vez mais devagar, sem
            // chegar ao fim da faixa antes da etapa terminar (como no Chrome)
            double t = _relogio.Elapsed.TotalSeconds - _inicioEtapa;
            double tau = Math.Max(4, (_fim - _inicio) * 1.5);
            double alvo = _inicio + (_fim - _inicio) * 0.92 * (1 - Math.Exp(-t / tau));
            _exibido += (Math.Max(alvo, _exibido) - _exibido) * 0.15;
        }
        else if (_estado == Estado.Concluido)
        {
            _exibido += (100 - _exibido) * 0.25;
        }
        Invalidate();
    }

    private void Terminou(int codigo)
    {
        CodigoSaida = codigo;
        LerProgresso();  // pega um "erro|..." gravado no último instante
        try { File.Delete(_arquivoProgresso); } catch { }
        if (codigo == 0)
        {
            _estado = Estado.Concluido;
            _status = "";
            Invalidate();
            if (_escondida)
            {
                Close();  // o usuário fechou a janela: termina em segundo plano, sem abrir o NuPDF
                return;
            }
            var fechar = new System.Windows.Forms.Timer { Interval = 1400 };
            fechar.Tick += (o, e) => { fechar.Stop(); AbrirNuPDF(); Close(); };
            fechar.Start();
        }
        else
        {
            _timer.Stop();
            _estado = Estado.Erro;
            if (_erro.Length == 0)
                _erro = "Ocorreu um erro durante a instalação (código " + codigo + "). " +
                        "Verifique a conexão com a internet e tente novamente.";
            if (_escondida) { Close(); return; }
            Invalidate();
        }
    }

    private static void AbrirNuPDF()
    {
        try
        {
            string exe = Path.Combine(Programa.PastaApp, "NuPDF.exe");
            if (File.Exists(exe))
                Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = Programa.PastaApp, UseShellExecute = false });
            else
                Process.Start(new ProcessStartInfo(Path.Combine(Programa.PastaApp, @"python\pythonw.exe"), "main.py")
                    { WorkingDirectory = Programa.PastaApp, UseShellExecute = false });
        }
        catch { }
    }

    private static void AbrirLog()
    {
        try
        {
            var log = new DirectoryInfo(Path.GetTempPath()).GetFiles("Setup Log*.txt")
                .OrderByDescending(f => f.LastWriteTime).FirstOrDefault();
            if (log != null) Process.Start("notepad.exe", Programa.Citar(log.FullName));
        }
        catch { }
    }

    // ------------------------------------------------------------------ áreas clicáveis
    private Rectangle RetFechar { get { return new Rectangle(ClientSize.Width - E(44), E(8), E(36), E(30)); } }
    private Rectangle RetMinimizar { get { return new Rectangle(ClientSize.Width - E(82), E(8), E(36), E(30)); } }
    private Rectangle RetTentar { get { return new Rectangle(ClientSize.Width / 2 - E(156), E(204), E(150), E(36)); } }
    private Rectangle RetSair { get { return new Rectangle(ClientSize.Width / 2 + E(6), E(204), E(150), E(36)); } }
    private Rectangle RetLog { get { return new Rectangle(ClientSize.Width / 2 - E(50), E(250), E(100), E(20)); } }

    private string AreaEm(Point p)
    {
        if (RetFechar.Contains(p)) return "fechar";
        if (RetMinimizar.Contains(p)) return "minimizar";
        if (_estado == Estado.Erro)
        {
            if (RetTentar.Contains(p)) return "tentar";
            if (RetSair.Contains(p)) return "sair";
            if (RetLog.Contains(p)) return "log";
        }
        return "";
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        string area = AreaEm(e.Location);
        if (area != _hover)
        {
            _hover = area;
            Cursor = area.Length > 0 ? Cursors.Hand : Cursors.Default;
            Invalidate();
        }
    }

    protected override void OnMouseLeave(EventArgs e)
    {
        base.OnMouseLeave(e);
        _hover = "";
        Invalidate();
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button != MouseButtons.Left || AreaEm(e.Location).Length > 0) return;
        ReleaseCapture();  // arrastar a janela por qualquer ponto livre
        SendMessage(Handle, 0xA1 /* WM_NCLBUTTONDOWN */, (IntPtr)2 /* HTCAPTION */, IntPtr.Zero);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (e.Button != MouseButtons.Left) return;
        switch (AreaEm(e.Location))
        {
            case "fechar": Fechar(); break;
            case "minimizar": WindowState = FormWindowState.Minimized; break;
            case "tentar": Iniciar(); break;
            case "sair": Close(); break;
            case "log": AbrirLog(); break;
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        base.OnKeyDown(e);
        if (e.KeyCode == Keys.Escape && _estado == Estado.Erro) Close();
    }

    private void Fechar()
    {
        if (_estado == Estado.Instalando)
        {
            // interromper o Inno no meio deixaria a instalação pela metade: a janela
            // some e a instalação termina em segundo plano
            _escondida = true;
            Hide();
            return;
        }
        Close();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        // Alt+F4 / fechar pela barra de tarefas durante a instalação: mesmo comportamento do X
        if (_estado == Estado.Instalando && e.CloseReason == CloseReason.UserClosing)
        {
            e.Cancel = true;
            Fechar();
            return;
        }
        base.OnFormClosing(e);
    }

    // ------------------------------------------------------------------ desenho
    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        int w = ClientSize.Width;

        if (!Windows11())
            using (var caneta = new Pen(Borda))
                g.DrawRectangle(caneta, 0, 0, ClientSize.Width - 1, ClientSize.Height - 1);

        DesenharBotaoJanela(g, RetMinimizar, "minimizar");
        DesenharBotaoJanela(g, RetFechar, "fechar");

        int tamLogo = E(64);
        g.DrawImage(_logo, new Rectangle((w - tamLogo) / 2, E(40), tamLogo, tamLogo));

        string titulo, sub;
        Color corSub = Texto2;
        if (_estado == Estado.Concluido)
        {
            titulo = _atualizacao ? "NuPDF atualizado" : "NuPDF instalado";
            sub = "Abrindo o NuPDF…";
        }
        else if (_estado == Estado.Erro)
        {
            titulo = _atualizacao ? "Não foi possível atualizar o NuPDF" : "Não foi possível instalar o NuPDF";
            sub = _erro;
        }
        else
        {
            // as etapas (_status) só movem a barra; o texto fica fixo, sem detalhes técnicos
            titulo = _atualizacao ? "Atualizando NuPDF" : "Instalando NuPDF";
            sub = "Isso pode levar alguns minutos…";
        }

        using (var fTitulo = new Font("Segoe UI", 14.5f, FontStyle.Regular, GraphicsUnit.Point))
        using (var fSub = new Font("Segoe UI", 9.5f, FontStyle.Regular, GraphicsUnit.Point))
        {
            var centro = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Near,
                                            Trimming = StringTrimming.EllipsisCharacter };
            using (var b = new SolidBrush(Texto))
                g.DrawString(titulo, fTitulo, b, new RectangleF(E(20), E(118), w - E(40), E(32)), centro);
            using (var b = new SolidBrush(corSub))
                g.DrawString(sub, fSub, b, new RectangleF(E(36), E(152), w - E(72), E(48)), centro);
        }

        if (_estado == Estado.Erro)
        {
            DesenharBotao(g, RetTentar, "Tentar Novamente", Destaque, "tentar");
            DesenharBotao(g, RetSair, "Fechar", Cinza, "sair");
            using (var f = new Font("Segoe UI", 8.5f, _hover == "log" ? FontStyle.Underline : FontStyle.Regular))
            using (var b = new SolidBrush(Texto2))
                g.DrawString("Ver Detalhes", f, b, RetLog, new StringFormat { Alignment = StringAlignment.Center });
            return;
        }

        // barra de progresso fina, nas cores do NuPDF
        var trilho = new RectangleF(E(56), E(218), w - E(112), E(5));
        using (var b = new SolidBrush(Trilho))
            PreencherArredondado(g, b, trilho);
        float largura = (float)(trilho.Width * Math.Min(100, Math.Max(0, _exibido)) / 100.0);
        if (largura > trilho.Height)
            using (var b = new SolidBrush(Destaque))
                PreencherArredondado(g, b, new RectangleF(trilho.X, trilho.Y, largura, trilho.Height));
    }

    private void DesenharBotaoJanela(Graphics g, Rectangle r, string nome)
    {
        if (_hover == nome)
            using (var b = new SolidBrush(Hover))
                PreencherArredondado(g, b, r, E(6));
        using (var caneta = new Pen(Texto2, Math.Max(1f, 1.2f * _s)))
        {
            float cx = r.X + r.Width / 2f, cy = r.Y + r.Height / 2f, m = E(5);
            if (nome == "fechar")
            {
                g.DrawLine(caneta, cx - m, cy - m, cx + m, cy + m);
                g.DrawLine(caneta, cx - m, cy + m, cx + m, cy - m);
            }
            else
                g.DrawLine(caneta, cx - m, cy, cx + m, cy);
        }
    }

    private void DesenharBotao(Graphics g, Rectangle r, string texto, Color cor, string nome)
    {
        Color fundo = _hover == nome ? ControlPaint.Dark(cor, 0.05f) : cor;
        using (var b = new SolidBrush(fundo))
            PreencherArredondado(g, b, r, E(8));
        using (var f = new Font("Segoe UI Semibold", 9.5f))
        using (var b = new SolidBrush(Color.White))
            g.DrawString(texto, f, b, r, new StringFormat { Alignment = StringAlignment.Center,
                                                           LineAlignment = StringAlignment.Center });
    }

    private static void PreencherArredondado(Graphics g, Brush b, RectangleF r, float raio = -1)
    {
        if (raio < 0) raio = r.Height / 2;
        float d = Math.Min(raio * 2, Math.Min(r.Width, r.Height));
        using (var caminho = new GraphicsPath())
        {
            caminho.AddArc(r.X, r.Y, d, d, 180, 90);
            caminho.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            caminho.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            caminho.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            caminho.CloseFigure();
            g.FillPath(b, caminho);
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _timer.Dispose();
            _logo.Dispose();
        }
        base.Dispose(disposing);
    }
}
