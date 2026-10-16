using AstraAgent.Tray.Workforce;
using Xunit;

namespace AstraAgent.Service.Tests;

public class ForegroundSamplerTests
{
    [Theory]
    [InlineData("https://github.com/anthropics/claude", "github.com")]
    [InlineData("https://www.youtube.com/watch?v=abc123", "youtube.com")]   // www stripped, query dropped
    [InlineData("https://docs.google.com/document/d/xyz/edit", "docs.google.com")]
    [InlineData("github.com/foo/bar", "github.com")]                        // no scheme
    [InlineData("http://INSTAGRAM.com/", "instagram.com")]                   // lower-cased
    public void DomainFromUrl_keeps_only_the_host(string url, string expected)
    {
        Assert.Equal(expected, ForegroundSampler.DomainFromUrl(url));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("just some text")]
    public void DomainFromUrl_returns_null_for_non_urls(string? url)
    {
        Assert.Null(ForegroundSampler.DomainFromUrl(url));
    }

    [Fact]
    public void DomainFromUrl_never_leaks_a_path_or_query()
    {
        // The privacy guarantee: a token or reset link in the query must not survive.
        var domain = ForegroundSampler.DomainFromUrl(
            "https://bank.example.com/reset?token=SECRET123&user=rahul");
        Assert.Equal("bank.example.com", domain);
        Assert.DoesNotContain("SECRET123", domain!);
    }

    [Theory]
    [InlineData("https://github.com/anthropics/claude", "/anthropics/claude")]
    [InlineData("https://github.com/anthropics/claude?tab=readme&x=1", "/anthropics/claude")]  // query dropped
    [InlineData("https://docs.google.com/document/d/xyz/edit#heading", "/document/d/xyz/edit")]  // fragment dropped
    [InlineData("github.com/foo", "/foo")]
    public void PathFromUrl_keeps_the_path_but_never_the_query(string url, string expected)
    {
        Assert.Equal(expected, ForegroundSampler.PathFromUrl(url));
    }

    [Theory]
    [InlineData("https://github.com")]      // bare root -> no meaningful path
    [InlineData("https://github.com/")]
    [InlineData(null)]
    [InlineData("")]
    public void PathFromUrl_returns_null_for_a_bare_site(string? url)
    {
        Assert.Null(ForegroundSampler.PathFromUrl(url));
    }

    [Fact]
    public void PathFromUrl_never_contains_a_question_mark()
    {
        var path = ForegroundSampler.PathFromUrl(
            "https://bank.example.com/reset?token=SECRET123");
        Assert.Equal("/reset", path);
        Assert.DoesNotContain("SECRET123", path!);
        Assert.DoesNotContain("?", path!);
    }

    [Theory]
    [InlineData("chrome", true)]
    [InlineData("msedge", true)]
    [InlineData("firefox", true)]
    [InlineData("CHROME", true)]      // case-insensitive
    [InlineData("Code", false)]
    [InlineData("WINWORD", false)]
    [InlineData("explorer", false)]
    public void IsBrowser_recognises_known_browsers(string process, bool expected)
    {
        Assert.Equal(expected, ForegroundSampler.IsBrowser(process));
    }
}
