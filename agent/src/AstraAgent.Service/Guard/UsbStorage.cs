using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32;

namespace AstraAgent.Service.Guard;

/// <summary>
/// USB drives on this PC, by the ID of their USB mass-storage interface
/// (<c>USB\VID_xxxx&amp;PID_yyyy\&lt;serial&gt;</c>), and putting a changed USB policy into effect now.
///
/// <para>Security review 3b H2: company drives once blocked <c>USBSTOR\Disk</c>, which a USB 3 drive
/// using UASP never is (Windows lists it under SCSI). Every USB drive, either way, sits under a USB
/// interface of the mass-storage class, <c>USB\Class_08</c>, so that is what is blocked, and a
/// company drive is approved by that interface's ID. SD cards in a reader on the PCIe bus (not
/// USB) are not covered.</para>
///
/// <para>Live test (19 Nov): Windows applies these rules when a drive is installed or mounted, not
/// to one already in. So when the USB policy changes, each USB drive it affects is reinstalled:
/// asked to stop the way "Safely remove" does (a drive with files open refuses, and keeps the old
/// rule until it is unplugged), uninstalled, and found again under the new rules.</para>
/// </summary>
internal static class UsbStorage
{
    public const string InterfaceClass = @"USB\Class_08";
    const string EnumUsb = @"SYSTEM\CurrentControlSet\Enum\USB";
    static readonly string[] StorageServices = ["USBSTOR", "UASPStor"];

    /// <summary>Every USB drive Windows has installed here (present or not), at most 50.</summary>
    public static IReadOnlyList<SeenDrive> Known(RegistryKey root)
    {
        var drives = new List<SeenDrive>();
        try
        {
            var names = DiskNames(root);
            using var usb = root.OpenSubKey(EnumUsb);
            foreach (var hw in usb?.GetSubKeyNames() ?? [])
            {
                if (!hw.StartsWith("VID_", StringComparison.OrdinalIgnoreCase)) continue;
                using var h = usb!.OpenSubKey(hw);
                foreach (var instance in h?.GetSubKeyNames() ?? [])
                {
                    using var i = h!.OpenSubKey(instance);
                    if (i is null || !IsStorage(i)) continue;
                    var name = (i.GetValue("ContainerID") is string c && names.TryGetValue(c, out var n) ? n
                                : i.GetValue("DeviceDesc") as string is { } d ? d[(d.LastIndexOf(';') + 1)..] : hw).Trim();
                    drives.Add(new SeenDrive($@"USB\{hw}\{instance}", name.Length > 100 ? name[..100] : name,
                                             UniqueSerial: !(instance.Length > 1 && instance[1] == '&')));
                    if (drives.Count >= 50) return drives;
                }
            }
        }
        catch (Exception ex) when (ex is UnauthorizedAccessException or System.Security.SecurityException or IOException) { }
        return drives;
    }

    /// <summary>A USB mass-storage interface: its compatible IDs say so even when Windows refused it
    /// a driver (then it has no Service, live test 19 Nov: a blocked drive must still be listed, to
    /// be approved and reinstalled); its service says so otherwise.</summary>
    static bool IsStorage(RegistryKey device) =>
        (device.GetValue("CompatibleIDs") is string[] ids &&
         ids.Any(id => id.StartsWith(InterfaceClass, StringComparison.OrdinalIgnoreCase))) ||
        (device.GetValue("Service") is string svc && StorageServices.Contains(svc, StringComparer.OrdinalIgnoreCase));

    /// <summary>The names Windows shows for disks, by container (the physical device): the USB
    /// interface itself is only "USB Mass Storage Device".</summary>
    static Dictionary<string, string> DiskNames(RegistryKey root)
    {
        var names = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var bus in new[] { "USBSTOR", "SCSI" })
        {
            using var b = root.OpenSubKey($@"SYSTEM\CurrentControlSet\Enum\{bus}");
            foreach (var dev in b?.GetSubKeyNames() ?? [])
            {
                if (!dev.StartsWith("Disk", StringComparison.OrdinalIgnoreCase)) continue;
                using var d = b!.OpenSubKey(dev);
                foreach (var inst in d?.GetSubKeyNames() ?? [])
                {
                    using var i = d!.OpenSubKey(inst);
                    if (i?.GetValue("ContainerID") is string c && i.GetValue("FriendlyName") is string f) names.TryAdd(c, f);
                }
            }
        }
        return names;
    }

    /// <summary>The USB ID to allow for an approved drive. An approval made before this change
    /// names the disk (<c>USBSTOR\Disk&amp;…\&lt;serial&gt;&amp;0</c>); its USB interface has the same
    /// serial. Null when that drive was never seen on this PC.</summary>
    public static string? UsbIdFor(RegistryKey root, string approved)
    {
        if (approved.StartsWith(@"USB\", StringComparison.OrdinalIgnoreCase)) return approved;
        var serial = approved[(approved.LastIndexOf('\\') + 1)..];
        if (serial.EndsWith("&0", StringComparison.Ordinal)) serial = serial[..^2];
        return Known(root).FirstOrDefault(d => d.Id.EndsWith(@"\" + serial, StringComparison.OrdinalIgnoreCase))?.Id;
    }

    /// <summary>Reinstalls these drives where they are plugged in, so the current rules apply.
    /// Returns how many could not be (in use, or Windows refused); they keep the old rule until
    /// they are unplugged.</summary>
    public static int Reinstall(IEnumerable<string> ids)
    {
        int refused = 0, done = 0;
        foreach (var id in ids)
        {
            if (CM_Locate_DevNode(out var dev, id, LocateNormal) != Success) continue;   // not plugged in
            var veto = new StringBuilder(260);
            if (CM_Query_And_Remove_SubTree(dev, out _, veto, veto.Capacity, RemoveUiNotOk) != Success) { refused++; continue; }
            if (CM_Locate_DevNode(out var phantom, id, LocatePhantom) == Success) CM_Uninstall_DevNode(phantom, 0);
            done++;
        }
        if (done > 0 && CM_Locate_DevNode(out var root, null, LocateNormal) == Success)
            CM_Reenumerate_DevNode(root, ReenumerateSynchronous);
        return refused;
    }

    /// <summary>Plugged in and working (no problem code).</summary>
    public static bool Working(string id) =>
        CM_Locate_DevNode(out var dev, id, LocateNormal) == Success &&
        CM_Get_DevNode_Status(out var status, out var problem, dev, 0) == Success && problem == 0 && (status & DnStarted) != 0;

    const int Success = 0;
    const uint LocateNormal = 0, LocatePhantom = 1, RemoveUiNotOk = 1, ReenumerateSynchronous = 1, DnStarted = 0x8;

    [DllImport("cfgmgr32.dll", CharSet = CharSet.Unicode, EntryPoint = "CM_Locate_DevNodeW")]
    static extern int CM_Locate_DevNode(out uint devInst, string? deviceId, uint flags);

    [DllImport("cfgmgr32.dll", CharSet = CharSet.Unicode, EntryPoint = "CM_Query_And_Remove_SubTreeW")]
    static extern int CM_Query_And_Remove_SubTree(uint devInst, out int vetoType, StringBuilder vetoName, int nameLength, uint flags);

    [DllImport("cfgmgr32.dll")]
    static extern int CM_Uninstall_DevNode(uint devInst, uint flags);

    [DllImport("cfgmgr32.dll")]
    static extern int CM_Reenumerate_DevNode(uint devInst, uint flags);

    [DllImport("cfgmgr32.dll")]
    static extern int CM_Get_DevNode_Status(out uint status, out uint problem, uint devInst, uint flags);
}
