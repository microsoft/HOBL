// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#if WINDOWS
using System;
using System.Windows.Forms;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Net.Sockets;
using System.Net;
using System.Runtime.InteropServices;
using System.Threading;
using System.Xml.Linq;
using Newtonsoft.Json;
using System.Text;
using System.Numerics;
using Microsoft.Win32;
using System.Runtime;


namespace InputInject
{

    public enum SystemMetric
    {
        VirtualScreenWidth = 78, // CXVIRTUALSCREEN 0x0000004E 
        VirtualScreenHeight = 79, // CYVIRTUALSCREEN 0x0000004F 
    }

    public sealed class PerfClip
    {
        public required int Width { get; init; }
        public required int Height { get; init; }
        public required int Framerate { get; init; }
        public required string OutputDir { get; init; }
        public required int[] Buffer { get; init; }
        public required int NumFrames { get; init; }
        public required int[] RepeatFrame { get; init; }
    }

    public class Interop
    {
        public const int KEYEVENTF_KEYDOWN = 0x0000; // New definition
        public const int KEYEVENTF_EXTENDEDKEY = 0x0001; // Key down flag
        public const int KEYEVENTF_KEYUP = 0x0002; // Key up flag
        public const int VK_SHIFT = 0x10; // Shift key code
        public const int VK_CONTROL = 0x11; // Control key code
        public const int VK_ALT = 0x12; // Alt key code
        public const int VK_LWIN = 0x5b; // Left Win key code
        public const int MAPVK_VK_TO_VSC = 0x00; // Map virtual key to scan code

        public int NumScreens { get; private set; }
        
        public int[][] Bits { get; private set; }
        protected GCHandle[] BitsHandle { get; private set; }

        //public int[] VidBits { get; private set; }
        //protected GCHandle VidBitsHandle { get; private set; }
        public List<PerfClip> PerfClips { get; private set; } = new();
        private volatile bool _stopCapture = false;
        private DesktopDuplicationCapturer[]? _desktopDuplications;

        public int[] ScreenWidth { get; private set; }
        public int[] ScreenHeight { get; private set; }
        public int[] ScreenX { get; private set; }
        public int[] ScreenY { get; private set; }
        public double[] ScalingFactor { get; private set; }

        QOIEncoder Encoder { get; set; }
        Application _app;

        public Interop(Application app)
        {
            // Setup for screen shots. Need to call before referencing
            // any function/variable that relies on DPI awareness
            SetProcessDpiAwareness(2);

            _app = app;
            NumScreens = Screen.AllScreens.Length;

            _desktopDuplications = new DesktopDuplicationCapturer[NumScreens];
            for (uint i = 0; i < (uint)NumScreens; i++)
            {
                _desktopDuplications[i] = new DesktopDuplicationCapturer(i);
            }

            Bits = new int[NumScreens][];
            BitsHandle = new GCHandle[NumScreens];

            
            //VidBits = new int[(100 * 100) * 122500]; // 100px by 100px with max of 122500 frames (30min @ 60fps);
            //VidBitsHandle = new GCHandle();
            //VidBitsHandle = GCHandle.Alloc(VidBits, GCHandleType.Pinned);

            ScreenWidth = new int[NumScreens];
            ScreenHeight = new int[NumScreens];
            ScreenX = new int[NumScreens];
            ScreenY = new int[NumScreens];
            ScalingFactor = new double[NumScreens];
            int ScreenIndex = 0;

            // This method of getting screen resolution only works with a single monitor setup
            foreach (Screen screen in Screen.AllScreens)
            {
                const int ENUM_CURRENT_SETTINGS = -1;
                DEVMODE devMode = default;
                devMode.dmSize = (short)Marshal.SizeOf(devMode);
                EnumDisplaySettings(screen.DeviceName, ENUM_CURRENT_SETTINGS, ref devMode);
                ScreenWidth[ScreenIndex] = devMode.dmPelsWidth;
                ScreenHeight[ScreenIndex] = devMode.dmPelsHeight;
                ScreenX[ScreenIndex] = devMode.dmPositionX;
                ScreenY[ScreenIndex] = devMode.dmPositionY;

                ScalingFactor[ScreenIndex] = GetScalingFactor(screen);

                Console.WriteLine($"Device: {screen.DeviceName}");
                Console.WriteLine($"Real Resolution: {devMode.dmPelsWidth}x{devMode.dmPelsHeight}");
                Console.WriteLine($"Real X: {devMode.dmPositionX}, Real Y: {devMode.dmPositionY}");
                Console.WriteLine($"Virtual Resolution: {screen.Bounds.Width}x{screen.Bounds.Height}");
                Console.WriteLine($"Virtual X: {screen.Bounds.X}, Virtual Y: {screen.Bounds.Y}");
                Console.WriteLine($"Scaling Factor for {screen.DeviceName}: {ScalingFactor[ScreenIndex]}");
                Console.WriteLine();

                Bits[ScreenIndex] = new int[ScreenWidth[ScreenIndex] * ScreenHeight[ScreenIndex] * 4]; // 4 bytes per pixel (ARGB)
                BitsHandle[ScreenIndex] = GCHandle.Alloc(Bits[ScreenIndex], GCHandleType.Pinned);

                ScreenIndex++;
            }

            // // This method of getting screen resolution works with multiple monitors and virtual screen
            // ScreenWidth = GetSystemMetrics(SystemMetric.VirtualScreenWidth);
            // ScreenHeight = GetSystemMetrics(SystemMetric.VirtualScreenHeight);

            // Alternative way to get screen resolution, but was being erroneously scaled by Windows DPI settings on some systems
            // using (var graphics = Graphics.FromHwnd(IntPtr.Zero))
            // {
            //     ScreenWidth = (int)graphics.VisibleClipBounds.Width;
            //     ScreenHeight = (int)graphics.VisibleClipBounds.Height;
            // }

            // Console.WriteLine($"Screen resolution: {ScreenWidth} x {ScreenHeight}");
            // // Bits = new Int32[ScreenWidth * ScreenHeight];
            // Bits = new int[ScreenWidth * ScreenHeight * 4]; // Big enough to handle virtual resolution
            // BitsHandle = GCHandle.Alloc(Bits, GCHandleType.Pinned);
            Encoder = new QOIEncoder();
        }

        public byte[] Screenshot(double xFrac, double yFrac, double wFrac, double hFrac, Int64 screenIndex = 0)
        {
            if (screenIndex < 0 || screenIndex >= NumScreens)
            {
                throw new ArgumentOutOfRangeException(nameof(screenIndex), "Invalid screen index.");
            }

            if (Bits == null || Bits.Length <= screenIndex || Bits[screenIndex] == null)
            {
                throw new InvalidOperationException("Bits array is not initialized for the specified screen index.");
            }

                //Console.WriteLine("Screenshot start");
            int x = (int)((ScreenWidth[screenIndex] * xFrac) + ScreenX[screenIndex]);
            int y = (int)((ScreenHeight[screenIndex] * yFrac) + ScreenY[screenIndex]);
            int w = (int)(ScreenWidth[screenIndex] * wFrac);
            int h = (int)(ScreenHeight[screenIndex] * hFrac);
            Size imageSize = new Size(w, h);

            Console.WriteLine($"Screenshot Screen: {screenIndex}, sx, sy, sw, sh: {ScreenX[screenIndex]}, {ScreenY[screenIndex]}, {ScreenWidth[screenIndex]}, {ScreenHeight[screenIndex]}");
            Console.WriteLine($"Screenshot Screen: {screenIndex}, Region: {x}, {y}, {w}, {h}");

            #pragma warning disable CA1416
            int stride = w * 4; // Ensure stride matches the width and pixel format
            if (Bits[screenIndex].Length < stride * h)
            {
                throw new ArgumentException("Bits array size is insufficient for the specified dimensions.");
            }
            Bitmap Bitmap = new Bitmap(w, h, stride, PixelFormat.Format32bppPArgb, BitsHandle[screenIndex].AddrOfPinnedObject());
            Graphics g = Graphics.FromImage(Bitmap);
            g.CopyFromScreen(x, y, 0, 0, imageSize); // sourceX, sourceY, destX, destY, blockRegionSize
            Encoder.Encode(w, h, Bits[screenIndex], false, false); // Compress BMP to QOI format
            //Console.WriteLine("Screenshot end");
            return (Encoder.GetEncoded()[..Encoder.GetEncodedSize()]);
        }

        public int ContinuousScreenshot(Int64 x, Int64 y, Int64 w, Int64 h, string outputDir, Int64 screenIndex = 0, Int64 time_ms = 10000, Int64 framerate = 60)
        {

            if (_stopCapture)
            {
                _stopCapture = false; // reset for starting new capture
            }

            if (_desktopDuplications is null)
                throw new InvalidOperationException("Desktop duplication is not initialized.");

            if (screenIndex < 0 || screenIndex >= _desktopDuplications.Length)
                throw new ArgumentOutOfRangeException(nameof(screenIndex));

            // Make captures an even pixel count to simplify encoding
            w = w - (w % 2);
            h = h - (h % 2);


            // Allocate all vars up front to ensure memory is reserved and to avoid GC overhead during capture loop
            int desiredFrameTimeMs = (int)(1000 / framerate);      // Desired frame time in milliseconds
            int pixelsPerFrame = checked((int)w * (int)h);         // Number of pixels per frame
            int maxFrames = checked((int)((time_ms + desiredFrameTimeMs - 1) / desiredFrameTimeMs)); // max frames needed to cover the time at the desired framerate, rounding up

            // Check for potential overflow in buffer size calculation
            if (pixelsPerFrame <= 0 || maxFrames <= 0 || (long)pixelsPerFrame * maxFrames > int.MaxValue)
            {
                throw new InvalidOperationException($"Calculated buffer size is too large. Pixels per frame: {pixelsPerFrame}, Max frames: {maxFrames}, Total pixels: {(long)pixelsPerFrame * maxFrames} Max allowed: {int.MaxValue}");
            }

            int[] VidBits = new int[pixelsPerFrame * maxFrames];    // pre-allocate max possible size for all frames to avoid GC overhead during capture loop
            int[] scratchBits = new int[pixelsPerFrame];            // scratch buffer for each capture attempt, to avoid copying from pinned buffer on each attempt and to allow non-blocking capture attempts without overwriting main buffer
            
            int frameOffset = 0;    // byte offset in VidBits for the current frame
            int[] duplicateFrameCount = new int[maxFrames]; // Number of times frame has repeated due to no new frame
            int count = 0;          // Number of unique frames captured
            long nextTick;          // Timestamp for scheduling next capture to maintain target framerate
            long tickFreq = Stopwatch.Frequency;            // Stopwatch ticks per second
            long tickStep = tickFreq / framerate;           // target framerate Hz samples
            long now;               // Current timestamp
            long remainingTicks;    // Ticks until next capture
            int remainingMs;        // Milliseconds until next capture
            uint newFrameTimeout;   // Timeout for capturing a new frame

            DesktopDuplicationCapturer capturer = _desktopDuplications[screenIndex];
            Stopwatch stopwatch = Stopwatch.StartNew();

#pragma warning disable CA1416

            // Prime schedule so first iteration runs immediately
            nextTick = Stopwatch.GetTimestamp();

            while (stopwatch.ElapsedMilliseconds < time_ms && count < maxFrames && !_stopCapture)
            {

                // Capture attempt (may be a timeout / no new frame produced by DWM)
                if (count == 0)
                {
                    newFrameTimeout = 16; // allow a longer timeout for the first frame to ensure we get an initial sample, as the desktop duplication API may not have a new frame ready immediately
                }
                else
                {
                    newFrameTimeout = 0; // after the first frame, we want to capture as close to the target framerate as possible, so no timeout (non-blocking)
                }

                if (capturer.TryCaptureBgra32((int)x, (int)y, (int)w, (int)h, scratchBits, timeoutMilliseconds: newFrameTimeout))
                {
                    // New frame captured, copy to main buffer
                    Array.Copy(scratchBits, 0, VidBits, frameOffset, pixelsPerFrame);
                    count++;
                    frameOffset += pixelsPerFrame;
                }
                else
                {
                    // Repeat frame (no new frame available from DWM)
                    if (count > 0)
                    {
                        duplicateFrameCount[count - 1]++;
                    }
                    else 
                    {
                        duplicateFrameCount[0]++; // If we haven't captured any frames yet, count duplicates in the first frame's duplicate count so that timing is preserved when we eventually do capture the first frame
                    }
                }


                // Pace to framerate using a timestamp schedule (more stable than Sleep(remainingMs))
                nextTick += tickStep;
                while (true)
                {
                    now = Stopwatch.GetTimestamp();
                    remainingTicks = nextTick - now;
                    if (remainingTicks <= 0)
                        break;

                    // Sleep only when there's enough slack; otherwise spin briefly for accuracy.
                    remainingMs = (int)(remainingTicks * 1000 / tickFreq);
                    if (remainingMs > 1)
                    {
                        Thread.Sleep(remainingMs - 1);
                    }
                    else
                    {
                        Thread.SpinWait(50);
                    }
                }
            }

            // Trim buffers to actual number of frames captured and record metadata, minimize memory footprint
            int[] finalBuffer = new int[count * pixelsPerFrame];
            int[] finalDuplicateFrames = new int[count];
            Array.Copy(duplicateFrameCount, finalDuplicateFrames, count);
            Array.Copy(VidBits, finalBuffer, count * pixelsPerFrame);

            PerfClip clip = new PerfClip()
            {
                Width = (int)w,
                Height = (int)h,
                Framerate = (int)framerate,
                OutputDir = outputDir,
                Buffer = finalBuffer,
                NumFrames = count,
                RepeatFrame = finalDuplicateFrames
            };

            PerfClips.Add(clip);

            if (_stopCapture)
            {
                Console.WriteLine($"Capture stopped by user after {stopwatch.ElapsedMilliseconds} ms and {count} frames.");
                _stopCapture = false; // reset for next capture
            }
            return count;
        }


        public void WriteCapturesToDisk(string directory)
        {
            StopCapture(); // Ensure capture is stopped before writing to disk
            if (PerfClips.Count == 0)
            {
                Console.WriteLine("No captures to write.");
                return;
            }

            if (!Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            // Derive ffmpeg path from the same drive as this assembly
            string assemblyPath = System.Reflection.Assembly.GetExecutingAssembly().Location;
            string drive = Path.GetPathRoot(assemblyPath) ?? "C:\\";
            string ffmpegPath = Path.Combine(drive, "hobl_bin", "ffmpeg.exe");

            if (!File.Exists(ffmpegPath))
            {
                throw new FileNotFoundException($" ERROR - FFmpeg not found at expected path: {ffmpegPath}");
            }

            // Process clips one at a time and release memory as we go
            while (PerfClips.Count > 0)
            {
                PerfClip clip = PerfClips[0];
                PerfClips.RemoveAt(0);

                string clipDir = Path.Combine(directory, clip.OutputDir);
                Directory.CreateDirectory(clipDir);

                // Write metadata CSV
                StringBuilder sb = new StringBuilder();
                sb.AppendLine("FrameIndex,RepeatFrame");
                for (int i = 0; i < clip.NumFrames; i++)
                {
                    sb.AppendLine($"{i},{clip.RepeatFrame[i]}");
                }
                File.WriteAllText(Path.Combine(clipDir, "frame_times.csv"), sb.ToString());

                string videoPath = Path.Combine(clipDir, "capture.mp4");
                int pixelsPerFrame = checked(clip.Width * clip.Height);

                // Start FFmpeg process - pipe raw BGRA frames, output lossless H.264
                // -crf 0 enables lossless mode, -preset ultrafast for speed (lossless ignores quality tradeoffs)
                var ffmpegArgs = $"-y -f rawvideo -pixel_format bgra -video_size {clip.Width}x{clip.Height} -framerate {clip.Framerate} -i - -c:v libx264 -crf 0 -preset ultrafast -pix_fmt yuv444p \"{videoPath}\"";

                var psi = new ProcessStartInfo
                {
                    FileName = ffmpegPath,
                    Arguments = ffmpegArgs,
                    UseShellExecute = false,
                    RedirectStandardInput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                using var ffmpeg = Process.Start(psi);
                if (ffmpeg == null)
                {
                    throw new InvalidOperationException($" ERROR - Failed to start FFmpeg process at: {ffmpegPath}");
                }

                // Read stderr asynchronously to prevent blocking
                StringBuilder ffmpegOutput = new StringBuilder();
                ffmpeg.ErrorDataReceived += (sender, e) =>
                {
                    if (!string.IsNullOrEmpty(e.Data))
                    {
                        ffmpegOutput.AppendLine(e.Data);
                    }
                };
                ffmpeg.BeginErrorReadLine();

                using (var stdin = ffmpeg.StandardInput.BaseStream)
                {
                    byte[] frameBytes = new byte[pixelsPerFrame * 4]; // 4 bytes per pixel (BGRA)

                    for (int i = 0; i < clip.NumFrames; i++)
                    {
                        // Get frame pixels from buffer
                        int frameOffset = checked(i * pixelsPerFrame);
                        Buffer.BlockCopy(clip.Buffer, frameOffset * sizeof(int), frameBytes, 0, frameBytes.Length);

                        // Write frame multiple times if it was duplicated during capture
                        for (int j = 0; j <= clip.RepeatFrame[i]; j++)
                        {
                            stdin.Write(frameBytes, 0, frameBytes.Length);
                        }
                    }
                }

                ffmpeg.WaitForExit();

                if (ffmpeg.ExitCode != 0)
                {
                    Console.WriteLine($" ERROR - FFmpeg exited with code {ffmpeg.ExitCode}");
                    Console.WriteLine(ffmpegOutput.ToString());
                }
                else
                {
                    Console.WriteLine($"Lossless H.264 video saved to: {videoPath}");
                }

                // Clip goes out of scope here, allowing its Buffer to be collected
            }

            ClearCaptures(); // Clear any remaining captures and release memory
        }

        public void StopCapture()
        {
            _stopCapture = true;
        }
        public void ClearCaptures()
        {
            StopCapture();
            PerfClips.Clear();
            Encoder = new QOIEncoder(); // Release the large internal buffer by creating a fresh encoder

            // Reset staging textures in desktop duplication capturers
            if (_desktopDuplications != null)
            {
                foreach (var capturer in _desktopDuplications)
                {
                    capturer?.ResetStagingTexture();
                }
            }

            // Force full GC with LOH compaction
            GCSettings.LargeObjectHeapCompactionMode = GCLargeObjectHeapCompactionMode.CompactOnce;
            GC.Collect(GC.MaxGeneration, GCCollectionMode.Aggressive, blocking: true, compacting: true);
            GC.WaitForPendingFinalizers();
            GC.Collect(); // Collect objects freed by finalizers
            
            // Return memory to OS
            //SetProcessWorkingSetSize(Process.GetCurrentProcess().Handle, -1, -1);
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetProcessWorkingSetSize(IntPtr hProcess, nint dwMinimumWorkingSetSize, nint dwMaximumWorkingSetSize);

        public Int64 GetScreenWidth()
        {
            // Only supporting single screen for now
            return (ScreenWidth[0]);
        }

        public Int64 GetScreenHeight()
        {
            // Only supporting single screen for now
            return (ScreenHeight[0]);
        }

        public string GetScreenInfo()
        {
            // // Return width, height, scaling factor
            // object dpiValue = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\ThemeManager", "LastLoadedDPI", "96") ?? "96";
            // int DPI = int.TryParse(dpiValue.ToString(), out int parsedDPI) ? parsedDPI : 96;
            // float scale = (float)DPI / 96.0f;
            // string return_string = String.Format("{0},{1},{2:F3}", ScreenWidth, ScreenHeight, scale);
            // return (return_string);
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < NumScreens; i++)
            {
                // sb.AppendFormat("Screen {0}: {1}x{2}, Scaling Factor: {3:F3}\n", i, ScreenWidth[i], ScreenHeight[i], ScalingFactor[i]);
                // Using this format to maintain cmpatibility with previous single screen implementation
                sb.AppendFormat("{0},{1},{2};", ScreenWidth[i], ScreenHeight[i], ScalingFactor[i]);
            }
            return sb.ToString();
        }

        public void MoveTo(Int64 x, Int64 y, Int64 screenIndex = 0, bool moveCursor = false)
        {
            if (moveCursor)
            {
                MoveCursorToTargetAsync(x, y, screenIndex).GetAwaiter().GetResult();
            }
            else 
            {
                // SetPhysicalCursorPos((int)(ScreenX[screenIndex] + x),  (int)(ScreenY[screenIndex] + y));
                // Move the mouse using SendInput()
                INPUT[] data = new INPUT[1];
                data[0] = new INPUT();
                data[0].type = 0; // mouse input

                MouseInput ms = new MouseInput();
                ms.dwFlags = 0x8000 | 0x0001 | 0x4000; // MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK

                // Normalize coordinates to 0..65535
                int virtualScreenWidth = GetSystemMetrics(SystemMetric.VirtualScreenWidth);
                int virtualScreenHeight = GetSystemMetrics(SystemMetric.VirtualScreenHeight);

                ms.dx = (int)Math.Round((65535.0 * (ScreenX[screenIndex] + x - SystemInformation.VirtualScreen.Left)) / virtualScreenWidth);
                ms.dy = (int)Math.Round((65535.0 * (ScreenY[screenIndex] + y - SystemInformation.VirtualScreen.Top)) / virtualScreenHeight);

                data[0].ms = ms;

                SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
            }
        }


        private async Task MoveCursorToTargetAsync(Int64 x, Int64 y, Int64 screenIndex = 0)
        {
            INPUT[] data = new INPUT[1];
            data[0] = new INPUT();
            data[0].type = 0; // mouse input

            MouseInput ms = new MouseInput();
            ms.dwFlags = 0x8000 | 0x0001 | 0x4000; // MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_VIRTUALDESK

            // Normalize coordinates to 0..65535
            int virtualScreenWidth = GetSystemMetrics(SystemMetric.VirtualScreenWidth);
            int virtualScreenHeight = GetSystemMetrics(SystemMetric.VirtualScreenHeight);

            Point start = Cursor.Position;
            Point target = new Point((int)(ScreenX[screenIndex] + x), (int)(ScreenY[screenIndex] + y));
            int deltaX = target.X - start.X;
            int deltaY = target.Y - start.Y;
            double distance = Math.Sqrt((deltaX * deltaX) + (deltaY * deltaY));
            int pointCount = Math.Clamp((int)(distance / 6) + 2, 10, 250);
            Point[] path = MousePathGenerator.Generate(start, target, pointCount);

            await Task.Run(() =>
            {
                using HighResolutionPeriodicTimer timer = new(TimeSpan.FromMilliseconds(8));

                for (int index = 1; index < path.Length; index++)
                {
                    if (index > 1)
                    {
                        timer.WaitForNextTick();
                    }

                    ms.dx = (int)Math.Round((65535.0 * (ScreenX[screenIndex] + path[index].X - SystemInformation.VirtualScreen.Left)) / virtualScreenWidth);
                    ms.dy = (int)Math.Round((65535.0 * (ScreenY[screenIndex] + path[index].Y - SystemInformation.VirtualScreen.Top)) / virtualScreenHeight);
                    data[0].ms = ms;
                    SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
                }
            });
        }


        public void MoveBy(Int64 x, Int64 y, bool moveCursor = false)
        {
            if (moveCursor)
            {
                // x and y are relative to the current cursor position.
                // Calculate the absolute target position and move the cursor there.
                Int64 ax = Cursor.Position.X + x;
                Int64 ay = Cursor.Position.Y + y;
                MoveCursorToTargetAsync(ax, ay, 0).GetAwaiter().GetResult();
            }
            else 
            {
                INPUT[] data = new INPUT[1];
                data[0] = new INPUT();
                data[0].type = 0; // mouse input

                MouseInput ms = new MouseInput();
                // For relative mouse movement (MOUSEEVENTF_MOVE without MOUSEEVENTF_ABSOLUTE), 
                // the coordinates should NOT be normalized to 0..65535. They are interpreted as relative pixel deltas.
                ms.dwFlags = 0x0001; // MOUSEEVENTF_MOVE (relative move)

                ms.dx = (int)x;
                ms.dy = (int)y;

                data[0].ms = ms;

                SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
            }
        }

        public void Tap(Int64 x, Int64 y, Int64 delay, bool primary, Int64 screenIndex = 0, bool moveCursor = false)
        {
            MoveTo(x, y, screenIndex, moveCursor);
            TouchDown(primary);
            Thread.Sleep((int)delay);
            TouchUp(primary);
        }

        public void TapDown(Int64 x, Int64 y, bool primary, Int64 screenIndex = 0, bool moveCursor = false)
        {
            MoveTo(x, y, screenIndex, moveCursor);
            TouchDown(primary);
        }

        public void TapUp(Int64 x, Int64 y, bool primary, Int64 screenIndex = 0, bool moveCursor = false)
        {
            MoveTo(x, y, screenIndex, moveCursor);
            TouchUp(primary);
        }

        public void Scroll(Int64 x, Int64 y, Int64 delay, string direction, Int64 screenIndex = 0, bool moveCursor = false)
        {
            MoveTo(x, y, screenIndex, moveCursor);
            if (direction == "down")
            {
                MouseWheel((int)(delay * (-1)));
            }
            else if (direction == "up")
            {
                MouseWheel((int)delay);
            }
        }

        public void Type(string s, Int64 delay)
        {
            bool control = false;
            bool alt = false;
            bool shift = false;
            bool win = false;
            long half_delay = (long)(delay / 2);
            long accum_delay = 0;
            DateTime startTime = DateTime.Now;

            foreach (char c in s)
            {
                uint vKey = (uint)VkKeyScanA(c);
                if (scanCodeMap.ContainsKey(c))
                {
                    vKey = (uint)scanCodeMap[c];
                }

                bool capital = (vKey & 0x100) != 0;
                vKey = (uint)(vKey & 0xff);
                if (c == '\ue009')
                {
                    if (control == false) {
                        KeyDown(VK_CONTROL);
                        control = true;
                    }
                    else
                    {
                        KeyUp(VK_CONTROL);
                        control = false;
                    }
                    accum_delay += half_delay;
                    sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue00a')
                {
                    if (alt == false)
                    {
                        KeyDown(VK_ALT);
                        alt = true;
                    }
                    else
                    {
                        KeyUp(VK_ALT);
                        alt = false;
                    }
                    accum_delay += half_delay;
                    sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue008')
                {
                    if (shift == false)
                    {
                        KeyDown(VK_SHIFT);
                        shift = true;
                    }
                    else
                    {
                        KeyUp(VK_SHIFT);
                        shift = false;
                    }
                    accum_delay += half_delay;
                    sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue03d')
                {
                    if (win == false)
                    {
                        KeyDown(VK_LWIN);
                        win = true;
                    }
                    else
                    {
                        KeyUp(VK_LWIN);
                        win = false;
                    }
                    accum_delay += half_delay;
                    sleepTo(startTime, accum_delay);
                    continue;
                }
                if (capital)
                {
                    KeyDown(VK_SHIFT);
                }
                KeyDown(vKey);
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);  // Spend half the specified delay holding the key down
                KeyUp(vKey);
                if (capital)
                {
                    KeyUp(VK_SHIFT);
                }
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);  // Spend the other half of the specified delay in-between stroke
            }
            if (shift)
            {
                KeyUp(VK_SHIFT);
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);
                shift = false;
            }
            if (alt)
            {
                KeyUp(VK_ALT);
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);
                alt = false;
            }
            if (control)
            {
                KeyUp(VK_CONTROL);
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);
                control = false;
            }
            if (win)
            {
                KeyUp(VK_LWIN);
                accum_delay += half_delay;
                sleepTo(startTime, accum_delay);
                win = false;
            }
        }

        public void KeyDown(uint vkey)
        {
            uint scanCode = MapVirtualKey(vkey, MAPVK_VK_TO_VSC);
            // Console.WriteLine($"KeyDown: {vkey} ScanCode: {scanCode}");
            uint flags = KEYEVENTF_KEYDOWN | 0x8;
            if (IsExtended(vkey))
            {
                // Console.WriteLine($"Extended");
                flags |= KEYEVENTF_EXTENDEDKEY;
            }
            keybd_event((byte)vkey, (byte)scanCode, flags, 0);
        }
        public void KeyUp(uint vkey)
        {
            uint scanCode = MapVirtualKey(vkey, MAPVK_VK_TO_VSC);
            uint flags = KEYEVENTF_KEYUP | 0x8;
            if (IsExtended(vkey))
            {
                flags |= KEYEVENTF_EXTENDEDKEY;
            }
            keybd_event((byte)vkey, (byte)scanCode, flags, 0);
        }

        public bool IsExtended(uint vkey)
        {
            // Extended keys are those with scan codes above 0x7f
            // and some specific keys like the left Windows key (0x5b)
            if ((vkey > 0x20 && vkey < 0x30) || vkey == 0x5b)
            {
                return true;
            }
            return false;
        }

        void sleepTo(DateTime startTime, long targetDelay)
        {
            DateTime now = DateTime.Now;
            TimeSpan span = now.Subtract(startTime);
            long delayTilNow = (long)(span.TotalSeconds * 1000);
            long delay = targetDelay - delayTilNow;
            if (delay > 0)
            {
                Thread.Sleep((int)delay);
            }
        }

        public void WindowMove(Int64 delay, Int64 screenIndex = 0)
        {
            IntPtr hwnd = GetForegroundWindow();

            if (hwnd == IntPtr.Zero)
                return;

            var i = 0;
            while (i++ < 4)
            {
                Screen screen = Screen.FromHandle(hwnd);

                if (Array.IndexOf(Screen.AllScreens, screen) == screenIndex)
                    break;

                // Win+Shift+Right
                Type("\ue03d\ue008\ue014", delay);
            }
        }

        public void WindowMaximize()
        {
            IntPtr hwnd = GetForegroundWindow();

            if (hwnd == IntPtr.Zero)
                return;
            
            const int SW_SHOWMAXIMIZED = 3;
            
            ShowWindow(hwnd, SW_SHOWMAXIMIZED);
        }


        // Legacy screenshot method
        Bitmap? takingScreenshot()
        {
            // //Create a new bitmap.
            // var bmpScreenshot = new Bitmap(ScreenWidth, ScreenHeight);

            // // Create a graphics object from the bitmap.
            // var g = Graphics.FromImage(bmpScreenshot);
            // Size ImageSize = new Size(ScreenWidth, ScreenHeight);

            // // Take the screenshot from the upper left corner to the right bottom corner.
            // g.CopyFromScreen(0,
            //                  0,
            //                  0,
            //                  0,
            //                  ImageSize);

            // return bmpScreenshot;
            return  null; // Placeholder return, as this method is not used in the current implementation
        }

        public void TouchDown(bool primary = true)
        {
            INPUT[] data = new INPUT[1];
            data[0] = new INPUT();
            data[0].type = 0; //mouse type;

            MouseInput ms = new MouseInput();
            if (primary == true)
            {
                ms.dwFlags = 0x0002; // left down
            }
            else
            {
                ms.dwFlags = 0x0008; // right down
            }
            data[0].ms = ms;

            SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
        }

        public void TouchUp(bool primary = true)
        {
            INPUT[] data = new INPUT[1];
            data[0] = new INPUT();
            data[0].type = 0; //mouse type;

            MouseInput ms = new MouseInput();
            if (primary == true)
            {
                ms.dwFlags = 0x0004; // left up
            }
            else
            {
                ms.dwFlags = 0x0010; // right up
            }
            data[0].ms = ms;

            SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
        }

        public void MouseWheel(int delay)
        {
            INPUT[] data = new INPUT[1];
            data[0] = new INPUT();
            data[0].type = 0; //mouse type;
            MouseInput ms = new MouseInput();
            ms.dwFlags = 0x0800; // wheel move

            ms.mouseData = (uint)delay; // direction and amount of movement
            data[0].ms = ms;

            SendInput(1, data, Marshal.SizeOf(typeof(INPUT)));
        }

        public void EventTag(string tag)
        {
            EtwLogger.Etw.Task(tag);
        }   

        [DllImport("user32.dll")]
        public static extern int GetSystemMetrics(SystemMetric metric);

        [DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        public static Size GetVirtualDisplaySize()
        {
            var width = GetSystemMetrics(SystemMetric.VirtualScreenWidth);
            var height = GetSystemMetrics(SystemMetric.VirtualScreenHeight);

            return new Size(width, height);
        }

        [DllImport("shcore.dll")]
        static extern uint SetProcessDpiAwareness(int value);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool SetPhysicalCursorPos(int x, int y);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool GetPhysicalCursorPos(ref Point lpPoint);

        [DllImport("user32.dll")]
        static extern bool EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);

        [DllImport("user32.dll")]
        internal static extern uint SendInput(uint nInputs,
            [MarshalAs(UnmanagedType.LPArray), In] INPUT[] pInputs, int cbSize);

        [DllImport("user32.dll")]
        static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);

        [DllImport("user32.dll")]
        static extern short VkKeyScanA(char c);

        [DllImport("user32.dll")]
        static extern uint MapVirtualKey(uint uCode, uint uMapType);

        // https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
        public static Dictionary<char, char> scanCodeMap = new Dictionary<char, char>() {
            {'\ue003', (char)0x08}, // BACKSPACE
            {'\ue004', (char)0x09}, // TAB
            {'\ue007', (char)0x0d}, // ENTER
            {'\ue00c', (char)0x1b}, // ESC
            {'\ue00d', (char)0x20}, // SPACE
            {'\ue00e', (char)0x21}, // PGUP
            {'\ue00f', (char)0x22}, // PGDN
            {'\ue010', (char)0x23}, // END
            {'\ue011', (char)0x24}, // HOME
            {'\ue012', (char)0x25}, // LEFT
            {'\ue013', (char)0x26}, // UP
            {'\ue014', (char)0x27}, // RIGHT
            {'\ue015', (char)0x28}, // DOWN
            {'\ue017', (char)0x2e}, // DELETE
            {'\ue031', (char)0x70}, // F1
            {'\ue032', (char)0x71}, // F2
            {'\ue033', (char)0x72}, // F3
            {'\ue034', (char)0x73}, // F4
            {'\ue035', (char)0x74}, // F5
            {'\ue036', (char)0x75}, // F6
            {'\ue037', (char)0x76}, // F7
            {'\ue038', (char)0x77}, // F8
            {'\ue039', (char)0x78}, // F9
            {'\ue03a', (char)0x79} // F10
        };

        [DllImport("User32.dll")]
        private static extern IntPtr MonitorFromPoint([In] System.Drawing.Point pt, [In] uint dwFlags);

        [DllImport("Shcore.dll")]
        private static extern IntPtr GetDpiForMonitor([In] IntPtr hmonitor, [In] DpiType dpiType, [Out] out uint dpiX, [Out] out uint dpiY);

        public enum DpiType
        {
            Effective = 0,
            Angular = 1,
            Raw = 2,
        }

        public static double GetScalingFactor(Screen screen)
        {
            var pnt = new System.Drawing.Point(screen.Bounds.Left + 1, screen.Bounds.Top + 1);
            var mon = MonitorFromPoint(pnt, 2);
            GetDpiForMonitor(mon, DpiType.Effective, out uint dpiX, out uint dpiY);
            return (double)dpiX / 96.0;
        }

    }

    [StructLayout(LayoutKind.Sequential)]
    public struct CGPOINT
    {
        public double x;
        public double y;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct DEVMODE
    {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 0x20)]
        public string dmDeviceName;
        public short dmSpecVersion;
        public short dmDriverVersion;
        public short dmSize;
        public short dmDriverExtra;
        public int dmFields;
        public int dmPositionX;
        public int dmPositionY;
        public int dmDisplayOrientation;
        public int dmDisplayFixedOutput;
        public short dmColor;
        public short dmDuplex;
        public short dmYResolution;
        public short dmTTOption;
        public short dmCollate;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 0x20)]
        public string dmFormName;
        public short dmLogPixels;
        public int dmBitsPerPel;
        public int dmPelsWidth;
        public int dmPelsHeight;
        public int dmDisplayFlags;
        public int dmDisplayFrequency;
        public int dmICMMethod;
        public int dmICMIntent;
        public int dmMediaType;
        public int dmDitherType;
        public int dmReserved1;
        public int dmReserved2;
        public int dmPanningWidth;
        public int dmPanningHeight;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT
    {
        public int type;
        public MouseInput ms;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KINPUT
    {
        public int type;
        public KeyboardInput ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public long x;
        public long y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MouseInput
    {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KeyboardInput
    {
        public int wVk;
        public int wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

}
#endif