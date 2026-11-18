using System.IO.Compression;
using System.Text;
using System.Text.Json;
using AstraAgent.GuardHost;
using UglyToad.PdfPig.Core;
using UglyToad.PdfPig.Content;
using UglyToad.PdfPig.Fonts.Standard14Fonts;
using UglyToad.PdfPig.Writer;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D3 / D5: the text inside uploaded documents and files on disk. Word and Excel are
/// always read; PDF only when the org chose it. Whatever cannot be read is null, which the
/// extension and the map treat as "could not check". The host answers with counts, never text.
/// </summary>
public sealed class DocumentsTests : IDisposable
{
    readonly string _root = Path.Combine(Path.GetTempPath(), "savio-docs-" + Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        if (Directory.Exists(_root)) Directory.Delete(_root, true);
    }

    static byte[] Pdf(params string[] lines)
    {
        var builder = new PdfDocumentBuilder();
        var page = builder.AddPage(PageSize.A4);
        var font = builder.AddStandard14Font(Standard14Font.Helvetica);
        var y = 750;
        foreach (var line in lines) { page.AddText(line, 12, new PdfPoint(40, y), font); y -= 20; }
        return builder.Build();
    }

    static byte[] Docx(string text)
    {
        var ms = new MemoryStream();
        using (var zip = new ZipArchive(ms, ZipArchiveMode.Create, leaveOpen: true))
        using (var w = new StreamWriter(zip.CreateEntry("word/document.xml").Open()))
            w.Write($"<w:document><w:body><w:p><w:t>{text}</w:t></w:p></w:body></w:document>");
        return ms.ToArray();
    }

    [Fact]
    public void A_pdf_is_read_only_when_the_org_chose_it()
    {
        var pdf = Pdf("Invoice for Asha", "PAN ABCPE1234F", "Card 4111 1111 1111 1111");
        var text = Documents.Text(pdf, ".pdf", pdf: true);
        Assert.NotNull(text);
        Assert.Contains("ABCPE1234F", text);
        Assert.Contains("4111 1111 1111 1111", text);
        Assert.Null(Documents.Text(pdf, ".pdf", pdf: false));
        Assert.Contains("ABCPE1234F", Documents.Text(Docx("PAN ABCPE1234F"), ".docx", pdf: false));
    }

    [Theory]
    [InlineData(".pdf")]
    [InlineData(".docx")]
    [InlineData(".xlsx")]
    public void A_file_that_is_not_what_its_name_says_could_not_be_checked(string ext) =>
        Assert.Null(Documents.Text(Encoding.UTF8.GetBytes("%PDF-1.7 not really, PAN ABCPE1234F"), ext, pdf: true));

    [Fact]
    public void Too_big_or_another_type_could_not_be_checked()
    {
        Assert.Null(Documents.Text(new byte[Documents.MaxBytes + 1], ".pdf", pdf: true));
        Assert.Null(Documents.Text(Docx("PAN ABCPE1234F"), ".doc", pdf: true));   // old Word: not read
    }

    static NativeHost.Response ScanFile(string name, byte[] bytes) =>
        NativeHost.Handle(JsonSerializer.SerializeToUtf8Bytes(new
        {
            type = "scan_file", name, data = Convert.ToBase64String(bytes), keywords = Array.Empty<string>(),
        }));

    [Fact]
    public void The_host_scans_an_uploaded_document_and_answers_with_counts_only()
    {
        foreach (var (name, bytes) in new[] { ("kyc.pdf", Pdf("PAN ABCPE1234F")), ("kyc.docx", Docx("PAN ABCPE1234F")) })
        {
            var r = ScanFile(name, bytes);
            Assert.True(r.Ok, name);
            Assert.Equal(1, r.Counts!["Pan"]);
            Assert.DoesNotContain("ABCPE1234F", JsonSerializer.Serialize(r));
        }
        Assert.False(ScanFile("kyc.pdf", Encoding.UTF8.GetBytes("broken")).Ok);
        Assert.False(ScanFile("photo.jpg", [1, 2, 3]).Ok);
        var notBase64 = NativeHost.Handle(Encoding.UTF8.GetBytes("""{"type":"scan_file","name":"a.pdf","data":"***"}"""));
        Assert.False(notBase64.Ok);
    }

    [Fact]
    public void The_weekly_map_reads_pdfs_only_when_asked()
    {
        Directory.CreateDirectory(_root);
        File.WriteAllBytes(Path.Combine(_root, "statement.pdf"), Pdf("Card 4111 1111 1111 1111"));
        Assert.Empty(Discovery.Run([_root], TimeSpan.Zero).Folders);
        var r = Discovery.Run([_root], TimeSpan.Zero, pdf: true);
        Assert.Equal(1, Assert.Single(r.Folders).Counts["PaymentCard"]);
    }
}
