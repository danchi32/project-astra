using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

namespace AstraAgent.Tray.Workforce;

/// <summary>Watches the cursor to judge whether mouse "activity" is real or a jiggler faking it.
///
/// Polls the cursor position and the mouse buttons once a second — no low-level hook, so nothing
/// that could read the keyboard, and nothing an antivirus treats as a keylogger. It records only
/// where the cursor is and whether a button was pressed; never the keyboard, never window
/// content. `TakeWindow` hands the accumulated poll data to JiggleHeuristic and resets.</summary>
public sealed class MouseActivityMonitor : IDisposable
{
    private const int VkLeft = 0x01, VkRight = 0x02, VkMiddle = 0x04;

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int X; public int Y; }

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT point);

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    private readonly object _lock = new();
    private readonly bool[] _down = new bool[3];
    private List<(int X, int Y)> _positions = new();
    private int _clicks;
    private System.Threading.Timer? _timer;

    public void Start() =>
        _timer = new System.Threading.Timer(_ => Poll(), null, TimeSpan.Zero, TimeSpan.FromSeconds(1));

    private void Poll()
    {
        try
        {
            if (!GetCursorPos(out var p))
                return;
            lock (_lock)
            {
                _positions.Add((p.X, p.Y));
                CheckButton(0, VkLeft);
                CheckButton(1, VkRight);
                CheckButton(2, VkMiddle);
            }
        }
        catch
        {
            // A failed poll just means one missing data point — never let it throw.
        }
    }

    // Counts a click as the down-edge of a button (up -> down), not every poll it is held.
    private void CheckButton(int index, int vKey)
    {
        var down = (GetAsyncKeyState(vKey) & 0x8000) != 0;
        if (down && !_down[index])
            _clicks++;
        _down[index] = down;
    }

    /// <summary>The positions and clicks since the last call, then reset for the next window.</summary>
    public (IReadOnlyList<(int X, int Y)> Positions, int Clicks) TakeWindow()
    {
        lock (_lock)
        {
            var positions = _positions;
            var clicks = _clicks;
            _positions = new List<(int, int)>();
            _clicks = 0;
            return (positions, clicks);
        }
    }

    public void Dispose() => _timer?.Dispose();
}
