using System.Runtime.InteropServices;

namespace AstraAgent.GuardHost;

/// <summary>
/// Security review (3b) M1: the PDF and Office readers parse files from anywhere, and a compressed
/// stream can inflate past any sensible size in seconds. The host puts itself in a Windows job
/// object with a memory limit when it starts, however it was started (the browser, the weekly
/// map, the USB check), so a file that needs more fails inside this process: "could not check",
/// never the PC's memory. Best effort: where it cannot (an older Windows that refuses nested
/// jobs), the host runs as before.
/// </summary>
internal static class MemoryCap
{
    public const long Limit = 1024L * 1024 * 1024;   // 1 GB: far above any 20 MB document's text

    public static bool Apply(long bytes = Limit)
    {
        var job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) return false;
        var info = new ExtendedLimits { Basic = new BasicLimits { LimitFlags = ProcessMemory }, ProcessMemoryLimit = (UIntPtr)bytes };
        // The handle stays open for the life of the process: closing it would end the job's hold.
        return SetInformationJobObject(job, ExtendedLimitInformation, ref info, Marshal.SizeOf<ExtendedLimits>())
               && AssignProcessToJobObject(job, GetCurrentProcess());
    }

    const int ExtendedLimitInformation = 9;
    const uint ProcessMemory = 0x100;   // JOB_OBJECT_LIMIT_PROCESS_MEMORY

    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimits
    {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong R, W, O, RB, WB, OB; }

    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimits
    {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string? name);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimits info, int length);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll")]
    static extern IntPtr GetCurrentProcess();
}
