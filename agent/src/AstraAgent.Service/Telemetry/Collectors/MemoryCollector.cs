using System.Diagnostics;
using System.Runtime.InteropServices;

namespace AstraAgent.Service.Telemetry.Collectors;

public sealed class MemoryCollector(ILogger<MemoryCollector> logger) : IMemoryCollector
{
    public MemoryInfo GetMemoryInfo()
    {
        try
        {
            var status = new MEMORYSTATUSEX { dwLength = (uint)Marshal.SizeOf<MEMORYSTATUSEX>() };
            if (GlobalMemoryStatusEx(ref status))
            {
                var totalMb = (long)(status.ullTotalPhys / 1024 / 1024);
                var availMb = (long)(status.ullAvailPhys / 1024 / 1024);
                return new MemoryInfo(totalMb, totalMb - availMb);
            }
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Memory collection via GlobalMemoryStatusEx failed");
        }

        // Fallback via PerformanceCounters
        try
        {
            using var avail = new PerformanceCounter("Memory", "Available MBytes");
            var availMb = (long)avail.NextValue();
            // Total from WMI as a last resort when P/Invoke fails
            return new MemoryInfo(0, availMb);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "Memory fallback collection failed");
            return new MemoryInfo(0, 0);
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct MEMORYSTATUSEX
    {
        public uint dwLength;
        public uint dwMemoryLoad;
        public ulong ullTotalPhys;
        public ulong ullAvailPhys;
        public ulong ullTotalPageFile;
        public ulong ullAvailPageFile;
        public ulong ullTotalVirtual;
        public ulong ullAvailVirtual;
        public ulong ullAvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX lpBuffer);
}
