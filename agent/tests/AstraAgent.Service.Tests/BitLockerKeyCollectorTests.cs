using AstraAgent.Service.Telemetry.Collectors;
using Xunit;

namespace AstraAgent.Service.Tests;

/// <summary>BitLocker key escrow — only well-formed recovery passwords leave the device, once.</summary>
public class BitLockerKeyCollectorTests
{
    private const string Password = "123456-234567-345678-456789-567890-678901-789012-890123";

    [Fact]
    public void A_48_digit_recovery_password_is_accepted()
        => Assert.True(BitLockerKeyCollector.IsRecoveryPassword(Password));

    [Theory]
    [InlineData("123456-234567-345678")]                                          // too short
    [InlineData("12345a-234567-345678-456789-567890-678901-789012-890123")]       // a letter
    [InlineData("")]
    public void Anything_else_is_not_a_recovery_password(string value)
        => Assert.False(BitLockerKeyCollector.IsRecoveryPassword(value));

    [Fact]
    public void Protector_ids_are_stored_in_one_form()
        => Assert.Equal("1a2b3c4d-1111-2222-3333-444455556666",
            BitLockerKeyCollector.NormalizeProtectorId("{1A2B3C4D-1111-2222-3333-444455556666}"));

    [Fact]
    public void A_non_guid_protector_id_is_refused()
        => Assert.Null(BitLockerKeyCollector.NormalizeProtectorId("{not-a-guid}"));

    [Fact]
    public void A_key_escrowed_in_this_run_is_not_sent_again()
    {
        var c = new BitLockerRecoveryKey("C:", "1a2b3c4d-1111-2222-3333-444455556666", Password);
        var d = new BitLockerRecoveryKey("D:", "9a2b3c4d-1111-2222-3333-444455556666", Password);
        var escrowed = new HashSet<string> { BitLockerKeyCollector.EscrowKey(c) };
        Assert.Equal([d], BitLockerKeyCollector.NotYetEscrowed([c, d], escrowed));
    }
}
