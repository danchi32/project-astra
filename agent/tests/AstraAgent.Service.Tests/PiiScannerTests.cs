using AstraAgent.Guard;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>
/// Phase 3 · D4 detectors. Three promises are under test:
/// <list type="number">
/// <item>Real data is found.</item>
/// <item>Look-alike numbers (order IDs, invoice numbers, timestamps) are not.</item>
/// <item>The result never carries the text it found.</item>
/// </list>
/// </summary>
public class PiiScannerTests
{
    static string ValidAadhaar(string first11)
    {
        for (int c = 0; c < 10; c++)
            if (PiiScanner.Verhoeff(first11 + c)) return first11 + c;
        throw new InvalidOperationException();
    }

    static string Spaced(string twelve) => $"{twelve[..4]} {twelve[4..8]} {twelve[8..]}";

    [Fact]
    public void Checksums_match_published_examples()
    {
        Assert.True(PiiScanner.Verhoeff("2363"));            // Verhoeff's worked example: 236 → 3
        Assert.False(PiiScanner.Verhoeff("2364"));
        Assert.True(PiiScanner.Luhn("4111111111111111"));    // Visa test number
        Assert.True(PiiScanner.Luhn("79927398713"));         // Luhn's worked example
        Assert.False(PiiScanner.Luhn("4111111111111112"));
        Assert.True(PiiScanner.GstinCheck("27AAPFU0939F1ZV"));
        Assert.False(PiiScanner.GstinCheck("27AAPFU0939F1ZX"));
    }

    [Fact]
    public void Finds_each_kind_in_ordinary_text()
    {
        var aadhaar = ValidAadhaar("23456789012");
        var text = $"""
            Dear team, employee KYC below.
            Aadhaar: {Spaced(aadhaar)}  PAN: ABCPE1234F  GSTIN 27AAPFU0939F1ZV
            Card 4111 1111 1111 1111 exp 12/28
            Call me on +91 98765 43210 or write to asha.k@example.co.in
            Salary to HDFC0001234 a/c 50100123456789
            """;
        var r = PiiScanner.Scan(text);
        Assert.Equal(1, r.Counts[Finding.Aadhaar]);
        Assert.Equal(1, r.Counts[Finding.Pan]);
        Assert.Equal(1, r.Counts[Finding.Gstin]);
        Assert.Equal(1, r.Counts[Finding.PaymentCard]);
        Assert.Equal(1, r.Counts[Finding.IndianMobile]);
        Assert.Equal(1, r.Counts[Finding.Email]);
        Assert.Equal(1, r.Counts[Finding.BankAccount]);
        Assert.False(r.Incomplete);
        Assert.True(r.Any);
    }

    [Fact]
    public void Bare_digit_runs_need_a_context_word()
    {
        // A Verhoeff-valid 12-digit number and a Luhn-valid 16-digit one, both unformatted:
        // order IDs and invoice numbers look exactly like this.
        var aadhaar = ValidAadhaar("34567890123");
        var orders = $"Order {aadhaar} shipped. Invoice 4111111111111111 paid.";
        var r = PiiScanner.Scan(orders);
        Assert.Equal(0, r.Counts[Finding.Aadhaar]);
        Assert.Equal(0, r.Counts[Finding.PaymentCard]);

        var labelled = $"aadhaar no {aadhaar}, visa 4111111111111111";
        var l = PiiScanner.Scan(labelled);
        Assert.Equal(1, l.Counts[Finding.Aadhaar]);
        Assert.Equal(1, l.Counts[Finding.PaymentCard]);
    }

    [Theory]
    [InlineData("Order 2345 6789 0123 has an invalid check digit")]  // formatted, but Verhoeff fails
    [InlineData("Timestamp 1700000000 and 1700000000123")]           // starts with 1: not a mobile
    [InlineData("Part ABCDE1234F1 is a SKU")]                         // PAN inside a longer token
    [InlineData("Ref 0000 0000 0000 0000 and 4444444444444444 card")] // all-same digits
    [InlineData("HDFC0001234 branch opens at 9")]                     // IFSC without an account
    [InlineData("Version 10.0.22631.4317 build")]
    public void Look_alikes_are_not_reported(string text)
    {
        var r = PiiScanner.Scan(text);
        Assert.Equal(0, r.Total);
    }

    [Fact]
    public void Non_ascii_digits_are_not_treated_as_numbers()
    {
        // Devanagari digits: .NET's \d would match these; the detectors use [0-9] on purpose.
        var r = PiiScanner.Scan("आधार २३४५ ६७८९ ०१२३ फ़ोन ९८७६५४३२१०");
        Assert.Equal(0, r.Counts[Finding.Aadhaar]);
        Assert.Equal(0, r.Counts[Finding.IndianMobile]);
    }

    [Fact]
    public void A_contact_list_is_recognised_and_prose_is_not()
    {
        var rows = string.Join('\n', Enumerable.Range(0, 30).Select(i => $"Customer {i},+91 98765{i:00000},c{i}@example.com"));
        Assert.True(PiiScanner.Scan(rows).ContactList);

        var prose = string.Join('\n', Enumerable.Range(0, 30).Select(i => $"Line {i} of an ordinary report about quarterly numbers."));
        Assert.False(PiiScanner.Scan(prose + "\nContact: ops@example.com").ContactList);
    }

    [Fact]
    public void Keywords_match_whole_words_case_insensitively_and_literally()
    {
        var keywords = new[] { "Project Falcon", "c++", "merger", "", new string('x', 101) };
        var r = PiiScanner.Scan("Notes on PROJECT FALCON. We use C++ daily. Mergers are rare.", keywords);
        Assert.Equal(new[] { 0, 1 }, r.KeywordHits);   // "merger" is not a whole word in "Mergers"
    }

    [Fact]
    public void The_result_never_contains_the_input()
    {
        var aadhaar = ValidAadhaar("45678901234");
        var text = $"Aadhaar {Spaced(aadhaar)} PAN ABCPE1234F";
        var r = PiiScanner.Scan(text, new[] { "secret-word" });
        var rendered = System.Text.Json.JsonSerializer.Serialize(r);
        Assert.DoesNotContain(aadhaar[..4], rendered);
        Assert.DoesNotContain("ABCPE1234F", rendered);
        Assert.DoesNotContain("secret-word", rendered);
    }

    [Fact]
    public void Oversized_input_is_scanned_up_to_the_cap_and_flagged()
    {
        var big = new string('a', PiiScanner.MaxChars) + " ABCPE1234F";   // the PAN sits past the cap
        var r = PiiScanner.Scan(big);
        Assert.True(r.Truncated);
        Assert.Equal(0, r.Counts[Finding.Pan]);
        Assert.Equal(0, PiiScanner.Scan(null).Total);
    }
}
