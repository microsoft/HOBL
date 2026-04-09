#if WINDOWS
using System;
using System.Runtime.InteropServices;
using Vortice.Direct3D;
using Vortice.Direct3D11;
using Vortice.DXGI;
using Vortice.Mathematics;
using static Vortice.Direct3D11.D3D11;

namespace InputInject;

internal sealed class DesktopDuplicationCapturer : IDisposable
{
    private readonly ID3D11Device _device;
    private readonly ID3D11DeviceContext _context;
    private readonly IDXGIOutputDuplication _duplication;

    private ID3D11Texture2D? _stagingTexture;
    private int _stagingWidth;
    private int _stagingHeight;

    public DesktopDuplicationCapturer(uint outputIndex)
    {
        // Note: this overload does not take a named "creationFlags" parameter in your Vortice version.
        // We pass BGRA support via DeviceCreationFlags.
        D3D11CreateDevice(
            adapter: null,
            driverType: DriverType.Hardware,
            flags: DeviceCreationFlags.BgraSupport,
            featureLevels: [],
            out ID3D11Device? device,
            out ID3D11DeviceContext? context).CheckError();

        _device = device ?? throw new InvalidOperationException("Failed to create D3D11 device.");
        _context = context ?? throw new InvalidOperationException("Failed to create D3D11 device context.");

        using var dxgiDevice = _device.QueryInterfaceOrNull<IDXGIDevice>()
            ?? throw new InvalidOperationException("Failed to query IDXGIDevice from D3D11 device.");

        using var adapter = dxgiDevice.GetAdapter();

        adapter.EnumOutputs(outputIndex, out IDXGIOutput output).CheckError();
        using (output)
        {
            using var output1 = output.QueryInterfaceOrNull<IDXGIOutput1>()
                ?? throw new InvalidOperationException("Failed to query IDXGIOutput1.");

            // _duplication = output1.DuplicateOutput(_device);
        }
    }

    public bool TryCaptureBgra32(int x, int y, int width, int height, Span<int> destination, uint timeoutMilliseconds = 16)
    {
        if (width <= 0)
            throw new ArgumentOutOfRangeException(nameof(width));

        if (height <= 0)
            throw new ArgumentOutOfRangeException(nameof(height));

        if (destination.Length < width * height)
            throw new ArgumentException("Destination buffer is too small.", nameof(destination));

        SharpGen.Runtime.Result acquire = _duplication.AcquireNextFrame(timeoutMilliseconds, out _, out IDXGIResource? desktopResource);
        if (acquire.Failure || desktopResource is null)
            return false;

        try
        {
            using var resource = desktopResource;
            using var desktopTexture = resource.QueryInterfaceOrNull<ID3D11Texture2D>();
            if (desktopTexture is null)
                return false;

            EnsureStaging(desktopTexture, width, height);

            var srcBox = new Box(x, y, 0, x + width, y + height, 1);
            _context.CopySubresourceRegion(_stagingTexture!, 0, 0, 0, 0, desktopTexture, 0, srcBox);

            MappedSubresource mapped = _context.Map(_stagingTexture!, 0, MapMode.Read, Vortice.Direct3D11.MapFlags.None);

            try
            {
                int dstRowBytes = checked(width * 4);
                int srcRowBytes = (int)mapped.RowPitch;

                unsafe
                {
                    byte* srcBase = (byte*)mapped.DataPointer;

                    fixed (int* dstPixels = destination)
                    {
                        byte* dstBase = (byte*)dstPixels;

                        // Copy rows 
                        for (int row = 0; row < height; row++)
                        {
                            byte* srcRow = srcBase + (row * srcRowBytes);
                            byte* dstRow = dstBase + (row * dstRowBytes);

                            Buffer.MemoryCopy(srcRow, dstRow, dstRowBytes, dstRowBytes);
                        }

                        // Force A=0xFF in case the source is BGRX.
                        uint* p = (uint*)dstPixels;
                        int pixelCount = checked(width * height);

                        for (int i = 0; i < pixelCount; i++)
                        {
                            p[i] |= 0xFF000000u;
                        }
                    }
                }
            }
            finally
            {
                _context.Unmap(_stagingTexture!, 0);
            }
        }
        finally
        {
            _duplication.ReleaseFrame();
        }

        return true;
    }

    private void EnsureStaging(ID3D11Texture2D desktopTexture, int width, int height)
    {
        if (_stagingTexture != null && _stagingWidth == width && _stagingHeight == height)
            return;

        _stagingTexture?.Dispose();

        Texture2DDescription desc = desktopTexture.Description;
        desc.Width = (uint)width;
        desc.Height = (uint)height;
        desc.Usage = ResourceUsage.Staging;
        desc.BindFlags = BindFlags.None;
        desc.CPUAccessFlags = CpuAccessFlags.Read;
        desc.MiscFlags = ResourceOptionFlags.None;

        _stagingTexture = _device.CreateTexture2D(desc);
        _stagingWidth = width;
        _stagingHeight = height;
    }

    public void ResetStagingTexture()
    {
        _stagingTexture?.Dispose();
        _stagingTexture = null;
        _stagingWidth = 0;
        _stagingHeight = 0;
    }

    public void Dispose()
    {
        _stagingTexture?.Dispose();
        _duplication.Dispose();
        _context.Dispose();
        _device.Dispose();
    }
}
#endif