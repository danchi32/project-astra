using AstraAgent.Service.Security;
using Xunit;

namespace AstraAgent.Service.Tests;

public class DpapiTokenStoreTests : IDisposable
{
    private readonly string _path = Path.Combine(
        Path.GetTempPath(), $"astra-test-{Guid.NewGuid():N}", "agent.credential");

    [Fact]
    public void SaveAndLoad_RoundTrips()
    {
        var store = new DpapiTokenStore(_path);
        store.Save("device-token-secret-value");
        Assert.Equal("device-token-secret-value", store.Load());
    }

    [Fact]
    public void Save_DoesNotWritePlaintext()
    {
        var store = new DpapiTokenStore(_path);
        store.Save("device-token-secret-value");
        var raw = File.ReadAllBytes(_path);
        Assert.DoesNotContain(
            "device-token-secret-value",
            System.Text.Encoding.UTF8.GetString(raw));
    }

    [Fact]
    public void Load_MissingFile_ReturnsNull()
    {
        var store = new DpapiTokenStore(_path);
        Assert.Null(store.Load());
    }

    [Fact]
    public void Load_CorruptedFile_ReturnsNull()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        File.WriteAllBytes(_path, [1, 2, 3, 4, 5]);
        var store = new DpapiTokenStore(_path);
        Assert.Null(store.Load());
    }

    [Fact]
    public void Clear_RemovesStoredToken()
    {
        var store = new DpapiTokenStore(_path);
        store.Save("device-token-secret-value");
        store.Clear();
        Assert.Null(store.Load());
    }

    public void Dispose()
    {
        var dir = Path.GetDirectoryName(_path)!;
        if (Directory.Exists(dir))
            Directory.Delete(dir, recursive: true);
    }
}
