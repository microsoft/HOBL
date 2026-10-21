// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

#if MACOS
// using System.Drawing;
using System.Runtime.InteropServices;
using ObjCRuntime;
using System.Drawing;


namespace InputInject
{    
    [StructLayout(LayoutKind.Sequential)]
    public struct CGPOINT
    {
        public double x;
        public double y;
    }

    public class Interop
    {
        public const int VK_SHIFT = 0x38; // Shift key code
        public const int VK_CONTROL = 0x3B; // Control key code
        public const int VK_OPTION = 0x3A; // Option key code
        public const int VK_COMMAND = 0x37; // Command key code
        public const int VK_FUNCTION = 0x3F; // Function key code

        // public const int kCGEventFlagMaskShift = 0x00000001; // Shift key flag
        // public const int kCGEventFlagMaskControl = 0x00000002; // Control key flag
        // public const int kCGEventFlagMaskOption = 0x00000004; // Option key flag
        // public const int kCGEventFlagMaskCommand = 0x00000008; // Command key flag
        // public const int kCGEventFlagMaskSecondaryFn = 0x00000008; // Function key flag

        public const int kCGEventFlagMaskShift       = 0x00020000; // Shift key flag
        public const int kCGEventFlagMaskControl     = 0x00040000; // Control key flag
        public const int kCGEventFlagMaskAlternate   = 0x00080000; // Option key flag
        public const int kCGEventFlagMaskCommand     = 0x00100000; // Command key flag
        public const int kCGEventFlagMaskSecondaryFn = 0x00800000; // Function key flag

        private const int kCGEventLeftMouseDown = 1; // Define the constant for left mouse down event
        private const int kCGEventLeftMouseUp = 2; // Define the constant for left mouse up event
        private const int kCGEventRightMouseDown = 3; // Define the constant for right mouse down event
        private const int kCGEventRightMouseUp = 4; // Define the constant for right mouse up event
        private const int kCGEventMouseMoved = 5; // Define the constant for mouse moved event
        private const int kCGScrollEventUnitPixel = 0; // Define the constant for scroll event unit in pixels
        private const int kCGHIDEventTap = 0; // Define the constant for HID event tap

        public int[] Bits { get; private set; }
        protected GCHandle BitsHandle { get; private set; }
        public int ScreenWidth { get; private set; }
        public int ScreenHeight { get; private set; }
        public bool FirstTime { get; private set; }

        QOIEncoder Encoder { get; set; }
        CGPOINT point;
        public int VirtualScreenWidth { get; private set; }
        public int VirtualScreenHeight { get; private set; }
        Application _app;

        public Interop(Application app)
        {
            // NSApplication.Init();
            _app = app;
            ScreenWidth = CGDisplayPixelsWide(CGMainDisplayID());
            ScreenHeight = CGDisplayPixelsHigh(CGMainDisplayID());
            var imagePtr = CGDisplayCreateImage(CGMainDisplayID());
            if (imagePtr == IntPtr.Zero)
            {
                throw new Exception("Failed to create CGImage.");
            }
            CGImage? image = Runtime.GetINativeObject<CGImage>(imagePtr, false); // Retain the CGImage reference
            if (image == null)
            {
                throw new Exception("Failed to retrieve CGImage from pointer.");
            }

            VirtualScreenWidth = (int)image.Width;
            VirtualScreenHeight = (int)image.Height;
            Console.WriteLine($"Screen resolution: {ScreenWidth} x {ScreenHeight}");
            Console.WriteLine($"Virtual Screen resolution: {VirtualScreenWidth} x {VirtualScreenHeight}");
            // Bits = new Int32[ScreenWidth * ScreenHeight];
            Bits = new int[VirtualScreenWidth * VirtualScreenHeight]; // Big enough to handle virtual resolution
            BitsHandle = GCHandle.Alloc(Bits, GCHandleType.Pinned);
            Encoder = app.Encoder;
            FirstTime = true;
        }

        public byte[] Screenshot(double xFrac, double yFrac, double wFrac, double hFrac, Int64 screenIndex = 0)
        {
            //Console.WriteLine("Screenshot start");
            int x = (int)(ScreenWidth * xFrac);
            int y = (int)(ScreenHeight * yFrac);
            int w = (int)(ScreenWidth * wFrac);
            int h = (int)(ScreenHeight * hFrac);
            // Size imageSize = new Size(w, h);

            // NSApplication.Init();  // This is only needed when saving as PNG.

            // Capture screenshot using CoreGraphics
            Console.WriteLine($"Capturing rect: {x}, {y}, {w}, {h}");
            var imagePtr = CGDisplayCreateImageForRect(CGMainDisplayID(), new CGRect(x, y, w, h));
            if (imagePtr == IntPtr.Zero)
            {
                throw new Exception("Failed to create CGImage.");
            }
            CGImage? image = Runtime.GetINativeObject<CGImage>(imagePtr, false); // Retain the CGImage reference
            if (image == null)
            {
                throw new Exception("Failed to retrieve CGImage from pointer.");
            }

            // Mac virtual resolution is generally 2x the screen resolution, so scaling down by half still
            // gives us plenty of resolution, simplifies coordinate matching, and is a lot faster to transfer.
            Console.WriteLine("Scaling");
            image = ScaleImageByHalf(image);
            
            // Save as PNG for debugging.
            // SaveScreenshot(image, "/Users/powertest/test.png");

            Console.WriteLine("Width: " + image.Width);
            Console.WriteLine("Height: " + image.Height);
            Console.WriteLine("Bits per component: " + image.BitsPerComponent);
            Console.WriteLine("Bytes per row: " + image.BytesPerRow);

            // Get the raw data from the CGImage
            Console.WriteLine("Geting");
            IntPtr data = CGDataProviderCopyData(CGImageGetDataProvider(image.Handle));
            try
            {
                Console.WriteLine("Copying");
                int length = CFDataGetLength(data);

                // // Allocate a managed integer array to hold the raw data
                // int[] rawData = new int[length / 4]; // Assuming 4 bytes per pixel (RGBA)

                // Copy the data into the managed array
                Marshal.Copy(CFDataGetBytePtr(data), Bits, 0, length/4);

                Console.WriteLine("Encoding");
                Encoder.Encode((int)(image.BytesPerRow / 4), (int)image.Height, Bits, false, false); // Compress BMP to QOI format

                // Write QOI file locally for debugging
                // File.WriteAllBytes("/Users/powertest/test.qoi", Encoder.GetEncoded()[..Encoder.GetEncodedSize()]);

                Console.WriteLine("Returning");
                return (Encoder.GetEncoded()[..Encoder.GetEncodedSize()]);
            }
            finally
            {
                // Release buffers after return
                CFRelease(imagePtr); // Release the CGImage reference
                CFRelease(data); // Release the CGImage reference
            }
        }

        public int ContinuousScreenshot(Int64 x, Int64 y, Int64 w, Int64 h, string outputDir, Int64 screenIndex = 0, Int64 time_ms = 10000, Int64 framerate = 60)
        {
            // Not implemented for MacOS
            return 0;
        }

        public void WriteCapturesToDisk(string directory)
        {
            // Not implemented for MacOS
            return;
        }

        public void StopCapture()
        {
            // Not implemented for MacOS
            return;
        }

        public void ClearCaptures()
        {
            // Not implemented for MacOS
            return;
        }


        public Int64 GetScreenWidth()
        {
            return (ScreenWidth);
        }

        public Int64 GetScreenHeight()
        {
            return (ScreenHeight);
        }

        public string GetScreenInfo()
        {
            // Return width, height, scaling factor
            string return_string = String.Format("{0},{1},{2:F3};", ScreenWidth, ScreenHeight, 1.0);
            return (return_string);
        }

        public void MoveTo(Int64 x, Int64 y, Int64 screenIndex = 0, bool moveCursor = false)
        {
            if (moveCursor)
            {
                MoveCursorToTargetAsync(x, y, screenIndex).GetAwaiter().GetResult();
            }
            else 
            {
                point.x = x;
                point.y = y;
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventMouseMoved, point, 0);
                CGEventPost(0, mouseEvent);
                CFRelease(mouseEvent);
            }
        }


        private async Task MoveCursorToTargetAsync(Int64 x, Int64 y, Int64 screenIndex = 0)
        {
            IntPtr eventPtr = CGEventCreate(IntPtr.Zero);
            CGPOINT startCG = CGEventGetLocation(eventPtr);
            CGPOINT pathCG = new CGPOINT();
            Point start = new Point((int)startCG.x, (int)startCG.y);
            Point target = new Point((int)x, (int)y);
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

                    pathCG.x = path[index].X;
                    pathCG.y = path[index].Y;
                    var mouseEvent = CGEventCreateMouseEvent(0, kCGEventMouseMoved, pathCG, 0);
                    CGEventPost(0, mouseEvent);
                    CFRelease(mouseEvent);
                }
            });
            CFRelease(eventPtr);
        }


        public void MoveBy(Int64 x, Int64 y, bool moveCursor = false)
        {
            if (moveCursor)
            {
                // x and y are relative to the current cursor position.
                // Calculate the absolute target position and move the cursor there.
                IntPtr eventPtr = CGEventCreate(IntPtr.Zero);
                CGPOINT locStruct = CGEventGetLocation(eventPtr);
                Int64 ax = (int)(locStruct.x + x);
                Int64 ay = (int)(locStruct.y + y);
                MoveCursorToTargetAsync(ax, ay, 0).GetAwaiter().GetResult();
                CFRelease(eventPtr);
            }
            else 
            {
                IntPtr eventPtr = CGEventCreate(IntPtr.Zero);
                CGPOINT locStruct = CGEventGetLocation(eventPtr);
                point.x = (int)(locStruct.x + x);
                point.y = (int)(locStruct.y + y);
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventMouseMoved, point, 0);
                CGEventPost(0, mouseEvent);
                CFRelease(eventPtr);
                CFRelease(mouseEvent);
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
                // MouseWheel(0);
                MouseWheel((int)(delay * (-1)));
            }
            else if (direction == "up")
            {
                // MouseWheel(0);
                MouseWheel((int)delay);
            }
        }

        public void Type(string s, Int64 delay)
        {
            bool control = false;
            bool option = false;
            bool shift = false;
            bool command = false;
            bool function = false;
            long half_delay = (long)(delay / 2);
            long accum_delay = 0;
            int flags = 0;
            DateTime startTime = DateTime.Now;

            foreach (char c in s)
            {
                //Get scan code for character


                ushort vKey = 0;
                try
                {
                    vKey = MacOSKeyCodeMap[c];
                }
                catch (KeyNotFoundException)
                {
                    throw new Exception("Unsupported character: " + c);
                }
                // Console.WriteLine("vKey: {0:X}", (int)vKey);

                bool shifted = ShiftedMap.ContainsKey(c) && ShiftedMap[c];
                vKey = (ushort)(vKey & 0xff);
                if (c == '\ue009') // Control key
                {
                    if (control == false)
                    {
                        flags |= kCGEventFlagMaskControl;
                        KeyDown(VK_CONTROL);
                        control = true;
                    }
                    else
                    {
                        flags &= ~kCGEventFlagMaskControl;
                        KeyUp(VK_CONTROL, flags);
                        control = false;
                    }
                    accum_delay += half_delay;
                    _app.sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue00a') // Option key
                {
                    if (option == false)
                    {
                        flags |= kCGEventFlagMaskAlternate;
                        KeyDown(VK_OPTION);
                        option = true;
                    }
                    else
                    {
                        flags &= ~kCGEventFlagMaskAlternate;
                        KeyUp(VK_OPTION, flags);
                        option = false;
                    }
                    accum_delay += half_delay;
                    _app.sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue008') // Shift key
                {
                    if (shift == false)
                    {
                        flags |= kCGEventFlagMaskShift;
                        KeyDown(VK_SHIFT);
                        shift = true;
                    }
                    else
                    {
                        flags &= ~kCGEventFlagMaskShift;
                        KeyUp(VK_SHIFT, flags);
                        shift = false;
                    }
                    accum_delay += half_delay;
                    _app.sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue03d') // Command key
                {
                    if (command == false)
                    {
                        flags |= kCGEventFlagMaskCommand;
                        KeyDown(VK_COMMAND, flags);
                        command = true;
                    }
                    else
                    {
                        flags &= ~kCGEventFlagMaskCommand;
                        KeyUp(VK_COMMAND, flags);
                        command = false;
                    }
                    accum_delay += half_delay;
                    _app.sleepTo(startTime, accum_delay);
                    continue;
                }
                if (c == '\ue03e') // Function key
                {
                    if (function == false)
                    {
                        flags |= kCGEventFlagMaskSecondaryFn;
                        KeyDown(VK_FUNCTION, flags);
                        function = true;
                    }
                    else
                    {
                        flags &= ~kCGEventFlagMaskSecondaryFn;
                        KeyUp(VK_FUNCTION, flags);
                        function = false;
                    }
                    accum_delay += half_delay;
                    _app.sleepTo(startTime, accum_delay);
                    continue;
                }
                if (shifted)
                {
                    Console.WriteLine("shifted");
                    flags |= kCGEventFlagMaskShift;
                    KeyDown(VK_SHIFT, flags);
                    accum_delay += 25; // Delay needs to be added between Shift and character, or it the Shift doesn't take effect.
                    _app.sleepTo(startTime, accum_delay);
                }
                KeyDown(vKey, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);  // Spend half the specified delay holding the key down
                KeyUp(vKey, flags);
                if (shifted)
                {
                    flags &= ~kCGEventFlagMaskShift;
                    KeyUp(VK_SHIFT, flags);
                }
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);  // Spend the other half of the specified delay in-between stroke
            }
            if (shift)
            {
                flags &= ~kCGEventFlagMaskShift;
                KeyUp(VK_SHIFT, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);
                shift = false;
            }
            if (option)
            {
                flags &= ~kCGEventFlagMaskAlternate;
                KeyUp(VK_OPTION, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);
                option = false;
            }
            if (control)
            {
                flags &= ~kCGEventFlagMaskControl;
                KeyUp(VK_CONTROL, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);
                control = false;
            }
            if (command)
            {
                flags &= ~kCGEventFlagMaskCommand;
                KeyUp(VK_COMMAND, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);
                command = false;
            }
            if (function)
            {
                flags &= ~kCGEventFlagMaskSecondaryFn;
                KeyUp(VK_FUNCTION, flags);
                accum_delay += half_delay;
                _app.sleepTo(startTime, accum_delay);
                function = false;
            }
        }

        public void KeyDown(ushort vKey, int flags = 0)
        {
            CGPostKeyboardEvent(0, vKey, true); // Post the key down event
            return;
            // New way, but doesn't work consistently:
            IntPtr keyEvent = CGEventCreateKeyboardEvent(IntPtr.Zero, vKey, true);
            if (keyEvent == IntPtr.Zero)
            {
                throw new Exception("Failed to create keyboard event.");
            }
            try
            {
                // Console.WriteLine("Key: {0:X}, Flags: {1:X}", vKey, flags);
                // Set the flags for the event
                CGEventSetFlags(keyEvent, flags | CGEventGetFlags(keyEvent));
                // Post the event
                CGEventPost(kCGHIDEventTap, keyEvent);
            }
            finally
            {
                // Release the event
                CFRelease(keyEvent);
            }
        }       

        public void KeyUp(ushort vKey, int flags = 0)
        {
            CGPostKeyboardEvent(0, vKey, false); // Post the key down event
            return;
            // New way, but doesn't work consistently:
            IntPtr keyEvent = CGEventCreateKeyboardEvent(IntPtr.Zero, vKey, false);
            if (keyEvent == IntPtr.Zero)
            {
                throw new Exception("Failed to create keyboard event.");
            }
            try
            {
                // Set the flags for the event
                CGEventSetFlags(keyEvent, flags | CGEventGetFlags(keyEvent));
                // Post the event
                CGEventPost(kCGHIDEventTap, keyEvent);
            }
            finally
            {
                // Release the event
                CFRelease(keyEvent);
            }
        }       

        public void TouchDown(bool primary = true)
        {
            if (primary)
            {
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventLeftMouseDown, point, 0);
                CGEventPost(kCGHIDEventTap, mouseEvent);
                CFRelease(mouseEvent);
            }
            else
            {
                Console.WriteLine("Right mouse down");
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventRightMouseDown, point, 1);
                CGEventPost(kCGHIDEventTap, mouseEvent);
                CFRelease(mouseEvent);
            }
        }

        public void TouchUp(bool primary = true)
        {
            if (primary)
            {
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventLeftMouseUp, point, 0);
                CGEventPost(kCGHIDEventTap, mouseEvent);
                CFRelease(mouseEvent);
            }
            else
            {
                var mouseEvent = CGEventCreateMouseEvent(0, kCGEventRightMouseUp, point, 1);
                CGEventPost(kCGHIDEventTap, mouseEvent);
                CFRelease(mouseEvent);
            }
        }

        public void MouseWheel(int amount)
        {
            double speed = amount / 20; // This allows an amount of 720 to approximate 1 screen, same as Windows.
            double accum_delay = 0;
            DateTime startTime = DateTime.Now;

            while(Math.Abs(speed) > 1.0)
            {
                speed *= 0.95;
                IntPtr scroll = CGEventCreateScrollWheelEvent(
                    IntPtr.Zero,
                    kCGScrollEventUnitPixel,
                    1,
                    (int)speed
                );
                CGEventPost(kCGHIDEventTap, scroll);
                CFRelease(scroll);
                // Thread.Sleep(16);
                accum_delay += 16.666666667;
                _app.sleepTo(startTime, (long)accum_delay);
            }
        }

        public void WindowMove(Int64 delay, Int64 screenIndex = 0)
        {
            return; // not supported on MacOS
        }

        public void WindowMaximize()
        {
            return; // not supported on MacOS
        }

        public void EventTag(string tag)
        {
            return; // not supported on MacOS
        }

        public void SaveScreenshot(CGImage image, string filePath)
        {
            var folderPath = Path.GetDirectoryName(filePath);

            if (folderPath == null) return;
            
            // Ensure the directory exists
            Directory.CreateDirectory(folderPath);

            // Save the image as a PNG file
            using var stream = File.OpenWrite(filePath);
            var properties = new NSDictionary();
            var imageFormat = NSBitmapImageFileType.Png;

            // Create an NSBitmapImageRep from the CGImage
            using var bitmapRep = new NSBitmapImageRep(image);
            // Get the representation data
            var data = bitmapRep.RepresentationUsingTypeProperties(imageFormat, properties);

            // Save the data to the stream
            data.AsStream().CopyTo(stream);
        }

        public CGImage ScaleImageByHalf(CGImage sourceImage)
        {
            if (sourceImage == null)
                throw new ArgumentNullException(nameof(sourceImage));

            // Calculate new dimensions (half the original)
            nint originalWidth = sourceImage.Width;
            nint originalHeight = sourceImage.Height;
            nint scaledWidth = originalWidth / 2;
            nint scaledHeight = originalHeight / 2;

            // Use the original image’s bits per component and color space (or default to DeviceRGB)
            nint bitsPerComponent = sourceImage.BitsPerComponent;
            // CGColorSpace colorSpace = sourceImage.ColorSpace ?? CGColorSpace.CreateDeviceRGB();
            CGColorSpace colorSpace = CGColorSpace.CreateDeviceRGB();

            // This creates a 32-bit per pixel ARGB context with 8 bits per component.
            CGBitmapFlags bitmapInfo = CGBitmapFlags.ByteOrder32Little | (CGBitmapFlags)CGImageAlphaInfo.PremultipliedFirst;

            // Create a bitmap context for the scaled image.
            // Using IntPtr.Zero lets the system allocate the backing memory.
            using (var context = new CGBitmapContext(
                IntPtr.Zero,
                scaledWidth,
                scaledHeight,
                bitsPerComponent,
                0,                      // 0 means the system computes the bytes-per-row automatically
                colorSpace,
                bitmapInfo) // Use the same alpha info as the original image
            )
            {
                // Set a high interpolation quality for smooth scaling
                context.InterpolationQuality = CGInterpolationQuality.High;

                // Draw the source image into the context, stretching it into the new dimensions.
                context.DrawImage(new CGRect(0, 0, scaledWidth, scaledHeight), sourceImage);

                // Extract a new CGImage from the context
                var scaledImage = context.ToImage();
                if (scaledImage == null)
                {
                    throw new InvalidOperationException("Failed to create scaled image.");
                }
                return scaledImage;
            }
        }

        public static readonly Dictionary<char, ushort> MacOSKeyCodeMap = new Dictionary<char, ushort>
        {
            // Letters
            { 'a', 0x00 }, { 'b', 0x0B }, { 'c', 0x08 }, { 'd', 0x02 },
            { 'e', 0x0E }, { 'f', 0x03 }, { 'g', 0x05 }, { 'h', 0x04 },
            { 'i', 0x22 }, { 'j', 0x26 }, { 'k', 0x28 }, { 'l', 0x25 },
            { 'm', 0x2E }, { 'n', 0x2D }, { 'o', 0x1F }, { 'p', 0x23 },
            { 'q', 0x0C }, { 'r', 0x0F }, { 's', 0x01 }, { 't', 0x11 },
            { 'u', 0x20 }, { 'v', 0x09 }, { 'w', 0x0D }, { 'x', 0x07 },
            { 'y', 0x10 }, { 'z', 0x06 },

            // Capital Letters
            { 'A', 0x00 }, { 'B', 0x0B }, { 'C', 0x08 }, { 'D', 0x02 },
            { 'E', 0x0E }, { 'F', 0x03 }, { 'G', 0x05 }, { 'H', 0x04 },
            { 'I', 0x22 }, { 'J', 0x26 }, { 'K', 0x28 }, { 'L', 0x25 },
            { 'M', 0x2E }, { 'N', 0x2D }, { 'O', 0x1F }, { 'P', 0x23 },
            { 'Q', 0x0C }, { 'R', 0x0F }, { 'S', 0x01 }, { 'T', 0x11 },
            { 'U', 0x20 }, { 'V', 0x09 }, { 'W', 0x0D }, { 'X', 0x07 },
            { 'Y', 0x10 }, { 'Z', 0x06 },

            // Numbers
            { '0', 0x1D }, { '1', 0x12 }, { '2', 0x13 }, { '3', 0x14 },
            { '4', 0x15 }, { '5', 0x17 }, { '6', 0x16 }, { '7', 0x1A },
            { '8', 0x1C }, { '9', 0x19 },

            // Symbols above numbers
            { '!', 0x12 }, { '@', 0x13 }, { '#', 0x14 }, { '$', 0x15 },
            { '%', 0x17 }, { '^', 0x16 }, { '&', 0x1A }, { '*', 0x1C },
            { '(', 0x19 }, { ')', 0x1D },

            // Symbols
            { '-', 0x1B }, { '=', 0x18 }, { '[', 0x21 }, { ']', 0x1E },
            { '\\', 0x2A }, { ';', 0x29 }, { '\'', 0x27 }, { ',', 0x2B },
            { '.', 0x2F }, { '/', 0x2C },

            // Shifted Symbols
            { '_', 0x1B }, { '+', 0x18 }, { '{', 0x21 }, { '}', 0x1E },
            { '|', 0x2A }, { ':', 0x29 }, { '"', 0x27 }, { '<', 0x2B },
            { '>', 0x2F }, { '?', 0x2C },

            // Special Characters
            { '`', 0x32 }, { ' ', 0x31 }, // Space and Backtick

            // Function Keys
            { '\ue031', 0x7A }, // F1
            { '\ue032', 0x78 }, // F2
            { '\ue033', 0x63 }, // F3
            { '\ue034', 0x76 }, // F4
            { '\ue035', 0x60 }, // F5
            { '\ue036', 0x61 }, // F6
            { '\ue037', 0x62 }, // F7
            { '\ue038', 0x64 }, // F8
            { '\ue039', 0x65 }, // F9
            { '\ue03a', 0x6D }, // F10
            { '\ue03b', 0x67 }, // F11
            { '\ue03c', 0x6F }, // F12

            // Arrow Keys
            { '\ue012', 0x7B }, // Left
            { '\ue013', 0x7E }, // Up
            { '\ue014', 0x7C }, // Right
            { '\ue015', 0x7D }, // Down

            // Other Special Keys
            { '\b', 0x33 }, // Backspace
            { '\t', 0x30 }, // Tab
            { '\n', 0x24 }, // Return/Enter
            { '\ue003', 0x33 }, // Backspace (Delete on Mac)
            { '\ue004', 0x30 }, // Tab
            { '\ue007', 0x24 }, // Return/Enter
            { '\ue00c', 0x35 }, // Escape
            { '\ue00d', 0x31 }, // Space

            { '\ue008', 0x38 }, // Shift
            { '\ue009', 0x3B }, // Control
            { '\ue00a', 0x3A }, // Option
            { '\ue03d', 0x37 }, // Command  
            { '\ue03e', 0x3F }, // Fn key
 
            // // Function Keys
            // { '\uF704', 0x7A }, // F1
            // { '\uF705', 0x78 }, // F2
            // { '\uF706', 0x63 }, // F3
            // { '\uF707', 0x76 }, // F4
            // { '\uF708', 0x60 }, // F5
            // { '\uF709', 0x61 }, // F6
            // { '\uF70A', 0x62 }, // F7
            // { '\uF70B', 0x64 }, // F8
            // { '\uF70C', 0x65 }, // F9
            // { '\uF70D', 0x6D }, // F10
            // { '\uF70E', 0x67 }, // F11
            // { '\uF70F', 0x6F }, // F12

            // // Arrow Keys
            // { '\uF700', 0x7E }, // Up
            // { '\uF701', 0x7D }, // Down
            // { '\uF702', 0x7B }, // Left
            // { '\uF703', 0x7C }, // Right

            // // Other Special Keys
            // { '\t', 0x30 }, // Tab
            // { '\n', 0x24 }, // Return/Enter
            // { '\u001B', 0x35 } // Escape
        };

        public static readonly Dictionary<char, bool> ShiftedMap = new Dictionary<char, bool>
        {
            // Capital Letters
            { 'A', true }, { 'B', true }, { 'C', true }, { 'D', true },
            { 'E', true }, { 'F', true }, { 'G', true }, { 'H', true },
            { 'I', true }, { 'J', true }, { 'K', true }, { 'L', true },
            { 'M', true }, { 'N', true }, { 'O', true }, { 'P', true },
            { 'Q', true }, { 'R', true }, { 'S', true }, { 'T', true },
            { 'U', true }, { 'V', true }, { 'W', true }, { 'X', true },
            { 'Y', true }, { 'Z', true },

            // Symbols above numbers
            { '!', true }, { '@', true }, { '#', true }, { '$', true },
            { '%', true }, { '^', true }, { '&', true }, { '*', true },
            { '(', true }, { ')', true },

            // Shifted Symbols
            { '_', true }, { '+', true }, { '{', true }, { '}', true },
            { '|', true }, { ':', true }, { '"', true }, { '<', true },
            { '>', true }, { '?', true }
        };

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern IntPtr CGDisplayCreateImageForRect(uint displayId, CGRect rect);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern void CGEventSetFlags(IntPtr eventRef, int flags);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern int CGEventGetFlags(IntPtr eventRef);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern void CGPostKeyboardEvent(IntPtr source, ushort virtualKey, bool keyDown);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern IntPtr CGEventCreateMouseEvent(int source, int mouseType, CGPOINT mouseCursorPosition, int mouseButton);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern CGPOINT CGEventGetLocation(IntPtr eventRef);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern IntPtr CGEventCreate(IntPtr source);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern void CGEventPost(int eventType, IntPtr eventRef);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern IntPtr CGDisplayCreateImage(uint displayId);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern uint CGMainDisplayID();
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern int CGDisplayPixelsHigh(uint displayId);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        public static extern int CGDisplayPixelsWide(uint displayId);
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGImageGetWidth(IntPtr image);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGImageGetHeight(IntPtr image);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGImageGetBytesPerRow(IntPtr image);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGImageGetDataProvider(IntPtr image);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGDataProviderCopyData(IntPtr provider);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern void CFRelease(IntPtr cf);

        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGEventCreateScrollWheelEvent(IntPtr source, int units, int wheelCount, int wheel1);
        [DllImport("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")]
        private static extern int CFDataGetLength(IntPtr data);
        [DllImport("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")]
        private static extern IntPtr CFDataGetBytePtr(IntPtr data);

        [DllImport("/System/Library/Frameworks/Carbon.framework/Carbon")]
        private static extern IntPtr TISCopyCurrentKeyboardInputSource();

        [DllImport("/System/Library/Frameworks/Carbon.framework/Carbon")]
        private static extern IntPtr TISGetInputSourceProperty(IntPtr inputSource, IntPtr propertyKey);

        [DllImport("/System/Library/Frameworks/Carbon.framework/Carbon")]
        private static extern int UCKeyTranslate(
            IntPtr keyLayoutPtr,
            ushort virtualKeyCode,
            uint keyAction,
            uint modifierKeyState,
            uint keyboardType,
            uint keyTranslateOptions,
            ref uint deadKeyState,
            [Out] char[] unicodeString,
            uint unicodeStringLength,
            out uint actualStringLength);
        
        [DllImport("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")]
        private static extern IntPtr CGEventCreateKeyboardEvent(IntPtr source, ushort virtualKey, bool keyDown);
    }
}
#endif