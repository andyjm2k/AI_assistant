const fs = require("node:fs");
const path = require("node:path");
const { execFile } = require("node:child_process");

const DEFAULT_GRID_COLUMNS = 24;
const DEFAULT_GRID_ROWS = 16;
const MAX_GRID_COLUMNS = 96;
const MAX_GRID_ROWS = 64;
const POWERSHELL_TIMEOUT_MS = 15000;
const POWERSHELL_MAX_BUFFER = 12 * 1024 * 1024;

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, Math.max(0, Number(ms) || 0)));
}

function normalizeGrid(grid = {}) {
  const columns = Math.max(2, Math.min(MAX_GRID_COLUMNS, Math.round(Number(grid.columns) || DEFAULT_GRID_COLUMNS)));
  const rows = Math.max(2, Math.min(MAX_GRID_ROWS, Math.round(Number(grid.rows) || DEFAULT_GRID_ROWS)));
  return { columns, rows };
}

function normalizeHwnd(value) {
  const text = String(value || "").trim();
  if (!/^\d+$/.test(text)) {
    return "";
  }
  return text;
}

function gridColumnLabel(index) {
  let value = Math.max(0, Math.min(MAX_GRID_COLUMNS - 1, Math.round(Number(index) || 0))) + 1;
  let label = "";
  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }
  return label || "A";
}

function gridColumnIndex(label) {
  const normalized = String(label || "").trim().toUpperCase();
  if (!/^[A-Z]{1,2}$/.test(normalized)) {
    return -1;
  }
  let value = 0;
  for (let index = 0; index < normalized.length; index += 1) {
    value = value * 26 + normalized.charCodeAt(index) - 64;
  }
  return value - 1;
}

function encodePowerShell(script) {
  return Buffer.from(script, "utf16le").toString("base64");
}

function parsePowerShellJson(stdout) {
  const raw = String(stdout || "").trim();
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start < 0 || end < start) {
    throw new Error(raw || "PowerShell command returned no JSON.");
  }
  return JSON.parse(raw.slice(start, end + 1));
}

function cleanPowerShellText(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }
  if (!raw.includes("#< CLIXML") && !raw.includes("<Objs")) {
    return raw;
  }
  const errorParts = [];
  for (const match of raw.matchAll(/<S S="Error">([\s\S]*?)<\/S>/g)) {
    errorParts.push(match[1]);
  }
  const text = (errorParts.length ? errorParts.join(" ") : raw)
    .replace(/_x000D__x000A_/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return text || raw;
}

function runPowerShellJson(script, input = {}, options = {}) {
  const encodedInput = Buffer.from(JSON.stringify(input), "utf8").toString("base64");
  const wrappedScript = `
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ActionArgsJson = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("${encodedInput}"))
$ActionArgs = $ActionArgsJson | ConvertFrom-Json
${script}
`;
  return new Promise((resolve, reject) => {
    execFile(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encodePowerShell(wrappedScript)],
      {
        windowsHide: true,
        timeout: Math.max(1000, Number(options.timeoutMs) || POWERSHELL_TIMEOUT_MS),
        maxBuffer: Math.max(POWERSHELL_MAX_BUFFER, Number(options.maxBuffer) || 0)
      },
      (error, stdout, stderr) => {
        if (error) {
          const detail = cleanPowerShellText(stderr || stdout || error.message || error);
          reject(new Error(detail || "PowerShell action harness command failed."));
          return;
        }
        try {
          resolve(parsePowerShellJson(stdout));
        } catch (parseError) {
          reject(parseError);
        }
      }
    );
  });
}

const WINDOW_INFO_SCRIPT = `
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public struct CatbotActionRect {
  public int Left;
  public int Top;
  public int Right;
  public int Bottom;
}

public static class CatbotActionWindow {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out CatbotActionRect rect);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

[void] [CatbotActionWindow]::SetProcessDPIAware()

function Get-CatbotWindowInfo([IntPtr] $Handle) {
  if ($Handle -eq [IntPtr]::Zero -or -not [CatbotActionWindow]::IsWindow($Handle)) {
    throw "No valid foreground window was found."
  }
  $rect = New-Object CatbotActionRect
  if (-not [CatbotActionWindow]::GetWindowRect($Handle, [ref] $rect)) {
    throw "Could not read the target window bounds."
  }
  $width = [Math]::Max(0, $rect.Right - $rect.Left)
  $height = [Math]::Max(0, $rect.Bottom - $rect.Top)
  if ($width -lt 20 -or $height -lt 20) {
    throw "The target window is too small to capture."
  }
  $titleBuilder = New-Object System.Text.StringBuilder 512
  [void] [CatbotActionWindow]::GetWindowText($Handle, $titleBuilder, $titleBuilder.Capacity)
  [uint32] $processId = 0
  [void] [CatbotActionWindow]::GetWindowThreadProcessId($Handle, [ref] $processId)
  $processName = ""
  try {
    $processName = [System.Diagnostics.Process]::GetProcessById([int] $processId).ProcessName
  } catch {
    $processName = ""
  }
  return [PSCustomObject]@{
    hwnd = $Handle.ToInt64().ToString()
    title = $titleBuilder.ToString()
    pid = [int64] $processId
    processName = $processName
    rect = [PSCustomObject]@{
      x = $rect.Left
      y = $rect.Top
      width = $width
      height = $height
      right = $rect.Right
      bottom = $rect.Bottom
    }
  }
}

$targetHwnd = if ($ActionArgs.hwnd) { [IntPtr] ([Int64] $ActionArgs.hwnd) } else { [CatbotActionWindow]::GetForegroundWindow() }
Get-CatbotWindowInfo $targetHwnd | ConvertTo-Json -Compress -Depth 8
`;

const CAPTURE_WINDOW_SCRIPT = `
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public struct CatbotActionRect {
  public int Left;
  public int Top;
  public int Right;
  public int Bottom;
}

public static class CatbotActionWindow {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out CatbotActionRect rect);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

[void] [CatbotActionWindow]::SetProcessDPIAware()

function Get-CatbotWindowInfo([IntPtr] $Handle) {
  if ($Handle -eq [IntPtr]::Zero -or -not [CatbotActionWindow]::IsWindow($Handle)) {
    throw "No valid target window was found."
  }
  $rect = New-Object CatbotActionRect
  if (-not [CatbotActionWindow]::GetWindowRect($Handle, [ref] $rect)) {
    throw "Could not read the target window bounds."
  }
  $width = [Math]::Max(0, $rect.Right - $rect.Left)
  $height = [Math]::Max(0, $rect.Bottom - $rect.Top)
  if ($width -lt 20 -or $height -lt 20) {
    throw "The target window is too small to capture."
  }
  $titleBuilder = New-Object System.Text.StringBuilder 512
  [void] [CatbotActionWindow]::GetWindowText($Handle, $titleBuilder, $titleBuilder.Capacity)
  [uint32] $processId = 0
  [void] [CatbotActionWindow]::GetWindowThreadProcessId($Handle, [ref] $processId)
  $processName = ""
  try {
    $processName = [System.Diagnostics.Process]::GetProcessById([int] $processId).ProcessName
  } catch {
    $processName = ""
  }
  return [PSCustomObject]@{
    hwnd = $Handle.ToInt64().ToString()
    title = $titleBuilder.ToString()
    pid = [int64] $processId
    processName = $processName
    rect = [PSCustomObject]@{
      x = $rect.Left
      y = $rect.Top
      width = $width
      height = $height
      right = $rect.Right
      bottom = $rect.Bottom
    }
  }
}

function Draw-CatbotGrid($Graphics, [int] $Width, [int] $Height, [int] $Columns, [int] $Rows) {
  $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $headerHeight = [Math]::Max(22, [Math]::Min(34, [Math]::Round($Height * 0.045)))
  $headerWidth = [Math]::Max(30, [Math]::Min(48, [Math]::Round($Width * 0.04)))
  $cellWidth = $Width / [double] $Columns
  $cellHeight = $Height / [double] $Rows
  $linePen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(128, 255, 255, 255)), 1
  $strongPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(190, 82, 214, 139)), 2
  $headerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(150, 0, 0, 0))
  $labelBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(245, 255, 255, 255))
  $labelShadowBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(210, 0, 0, 0))
  $fontSize = [Math]::Max(7, [Math]::Min(10, [Math]::Round([Math]::Min($cellWidth / 4.6, $cellHeight / 3.2))))
  $font = New-Object System.Drawing.Font "Segoe UI", $fontSize, ([System.Drawing.FontStyle]::Bold)
  $format = New-Object System.Drawing.StringFormat
  $format.Alignment = [System.Drawing.StringAlignment]::Center
  $format.LineAlignment = [System.Drawing.StringAlignment]::Center

  $Graphics.FillRectangle($headerBrush, 0, 0, $Width, $headerHeight)
  $Graphics.FillRectangle($headerBrush, 0, ($Height - $headerHeight), $Width, $headerHeight)
  $Graphics.FillRectangle($headerBrush, 0, 0, $headerWidth, $Height)
  $Graphics.FillRectangle($headerBrush, ($Width - $headerWidth), 0, $headerWidth, $Height)

  for ($index = 0; $index -le $Columns; $index += 1) {
    $x = [Math]::Round($index * $cellWidth)
    $pen = if ($index % 4 -eq 0) { $strongPen } else { $linePen }
    $Graphics.DrawLine($pen, $x, 0, $x, $Height)
  }
  for ($index = 0; $index -le $Rows; $index += 1) {
    $y = [Math]::Round($index * $cellHeight)
    $pen = if ($index % 3 -eq 0) { $strongPen } else { $linePen }
    $Graphics.DrawLine($pen, 0, $y, $Width, $y)
  }

  function Get-CatbotColumnLabel([int] $Index) {
    $value = $Index + 1
    $label = ""
    while ($value -gt 0) {
      $value -= 1
      $label = [char] ([int] (65 + ($value % 26))) + $label
      $value = [Math]::Floor($value / 26)
    }
    return $label
  }

  for ($index = 0; $index -lt $Columns; $index += 1) {
    $label = Get-CatbotColumnLabel $index
    $rect = New-Object System.Drawing.RectangleF ([single] ($index * $cellWidth)), 0, ([single] $cellWidth), ([single] $headerHeight)
    $shadowRect = New-Object System.Drawing.RectangleF ($rect.X + 1), ($rect.Y + 1), $rect.Width, $rect.Height
    $Graphics.DrawString($label, $font, $labelShadowBrush, $shadowRect, $format)
    $Graphics.DrawString($label, $font, $labelBrush, $rect, $format)
    $bottomRect = New-Object System.Drawing.RectangleF ([single] ($index * $cellWidth)), ([single] ($Height - $headerHeight)), ([single] $cellWidth), ([single] $headerHeight)
    $bottomShadowRect = New-Object System.Drawing.RectangleF ($bottomRect.X + 1), ($bottomRect.Y + 1), $bottomRect.Width, $bottomRect.Height
    $Graphics.DrawString($label, $font, $labelShadowBrush, $bottomShadowRect, $format)
    $Graphics.DrawString($label, $font, $labelBrush, $bottomRect, $format)
  }
  for ($index = 0; $index -lt $Rows; $index += 1) {
    $label = ($index + 1).ToString()
    $rect = New-Object System.Drawing.RectangleF 0, ([single] ($index * $cellHeight)), ([single] $headerWidth), ([single] $cellHeight)
    $shadowRect = New-Object System.Drawing.RectangleF ($rect.X + 1), ($rect.Y + 1), $rect.Width, $rect.Height
    $Graphics.DrawString($label, $font, $labelShadowBrush, $shadowRect, $format)
    $Graphics.DrawString($label, $font, $labelBrush, $rect, $format)
    $rightRect = New-Object System.Drawing.RectangleF ([single] ($Width - $headerWidth)), ([single] ($index * $cellHeight)), ([single] $headerWidth), ([single] $cellHeight)
    $rightShadowRect = New-Object System.Drawing.RectangleF ($rightRect.X + 1), ($rightRect.Y + 1), $rightRect.Width, $rightRect.Height
    $Graphics.DrawString($label, $font, $labelShadowBrush, $rightShadowRect, $format)
    $Graphics.DrawString($label, $font, $labelBrush, $rightRect, $format)
  }

  $linePen.Dispose()
  $strongPen.Dispose()
  $headerBrush.Dispose()
  $labelBrush.Dispose()
  $labelShadowBrush.Dispose()
  $font.Dispose()
  $format.Dispose()
}

function Save-CatbotBitmap([System.Drawing.Bitmap] $Bitmap, [string] $Path, [string] $Format, [int] $Quality) {
  $normalizedFormat = ([string] $Format).ToLowerInvariant()
  if ($normalizedFormat -eq "jpg" -or $normalizedFormat -eq "jpeg") {
    $jpegCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" } | Select-Object -First 1
    if ($null -eq $jpegCodec) {
      $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Jpeg)
      return
    }
    $encoderParameters = New-Object System.Drawing.Imaging.EncoderParameters 1
    try {
      $boundedQuality = [Math]::Max(35, [Math]::Min(95, $Quality))
      $encoderParameters.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter -ArgumentList ([System.Drawing.Imaging.Encoder]::Quality), ([int64] $boundedQuality)
      $Bitmap.Save($Path, $jpegCodec, $encoderParameters)
    } finally {
      $encoderParameters.Dispose()
    }
    return
  }
  $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
}

$targetHwnd = if ($ActionArgs.hwnd) { [IntPtr] ([Int64] $ActionArgs.hwnd) } else { [CatbotActionWindow]::GetForegroundWindow() }
$info = Get-CatbotWindowInfo $targetHwnd
$outputPath = [string] $ActionArgs.outputPath
if (-not $outputPath) {
  throw "Capture output path is required."
}
$outputDirectory = [System.IO.Path]::GetDirectoryName($outputPath)
if ($outputDirectory) {
  [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}
$columns = [Math]::Max(2, [Math]::Min(52, [int] $ActionArgs.columns))
$rows = [Math]::Max(2, [Math]::Min(36, [int] $ActionArgs.rows))
$format = if ($ActionArgs.format) { ([string] $ActionArgs.format).ToLowerInvariant() } else { "png" }
$jpegQuality = [Math]::Max(35, [Math]::Min(95, [int] $ActionArgs.jpegQuality))
$maxImageWidth = [Math]::Max(0, [int] $ActionArgs.maxImageWidth)
$outputWidth = $info.rect.width
$outputHeight = $info.rect.height
if ($maxImageWidth -gt 0 -and $outputWidth -gt $maxImageWidth) {
  $scale = $maxImageWidth / [double] $outputWidth
  $outputWidth = [int] [Math]::Round($outputWidth * $scale)
  $outputHeight = [int] [Math]::Round($outputHeight * $scale)
}
$bitmap = $null
$graphics = $null
$sourceBitmap = $null
$sourceGraphics = $null
try {
  $bitmap = New-Object System.Drawing.Bitmap $outputWidth, $outputHeight, ([System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  if ($outputWidth -eq $info.rect.width -and $outputHeight -eq $info.rect.height) {
    $graphics.CopyFromScreen($info.rect.x, $info.rect.y, 0, 0, (New-Object System.Drawing.Size $info.rect.width, $info.rect.height))
  } else {
    $sourceBitmap = New-Object System.Drawing.Bitmap $info.rect.width, $info.rect.height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $sourceGraphics = [System.Drawing.Graphics]::FromImage($sourceBitmap)
    $sourceGraphics.CopyFromScreen($info.rect.x, $info.rect.y, 0, 0, (New-Object System.Drawing.Size $info.rect.width, $info.rect.height))
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighSpeed
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::Bilinear
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighSpeed
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighSpeed
    $graphics.DrawImage($sourceBitmap, 0, 0, $outputWidth, $outputHeight)
  }
  if ($ActionArgs.overlay -ne $false) {
    Draw-CatbotGrid $graphics $outputWidth $outputHeight $columns $rows
  }
  Save-CatbotBitmap $bitmap $outputPath $format $jpegQuality
} finally {
  if ($graphics) { $graphics.Dispose() }
  if ($bitmap) { $bitmap.Dispose() }
  if ($sourceGraphics) { $sourceGraphics.Dispose() }
  if ($sourceBitmap) { $sourceBitmap.Dispose() }
}

[PSCustomObject]@{
  hwnd = $info.hwnd
  title = $info.title
  pid = $info.pid
  processName = $info.processName
  rect = $info.rect
  grid = [PSCustomObject]@{
    columns = $columns
    rows = $rows
  }
  image = [PSCustomObject]@{
    width = $outputWidth
    height = $outputHeight
    format = $format
    jpegQuality = $jpegQuality
  }
  outputPath = $outputPath
} | ConvertTo-Json -Compress -Depth 8
`;

const INPUT_SCRIPT = `
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class CatbotActionInput {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out CatbotActionPoint point);
  [DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
  [DllImport("user32.dll")] public static extern uint SendInput(uint inputCount, CatbotActionInputRecord[] inputs, int inputSize);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extraInfo);

  public const int InputMouse = 0;
  public const uint MouseMove = 0x0001;
  public const uint MouseLeftDown = 0x0002;
  public const uint MouseLeftUp = 0x0004;
  public const uint MouseRightDown = 0x0008;
  public const uint MouseRightUp = 0x0010;
  public const uint MouseMiddleDown = 0x0020;
  public const uint MouseMiddleUp = 0x0040;
  public const uint MouseAbsolute = 0x8000;
  public const uint MouseVirtualDesk = 0x4000;

  public static uint SendMouse(uint flags, int dx, int dy) {
    CatbotActionInputRecord[] inputs = new CatbotActionInputRecord[1];
    inputs[0].type = InputMouse;
    inputs[0].mi.dx = dx;
    inputs[0].mi.dy = dy;
    inputs[0].mi.mouseData = 0;
    inputs[0].mi.dwFlags = flags;
    inputs[0].mi.time = 0;
    inputs[0].mi.dwExtraInfo = UIntPtr.Zero;
    return SendInput(1, inputs, Marshal.SizeOf(typeof(CatbotActionInputRecord)));
  }
}

public struct CatbotActionPoint {
  public int X;
  public int Y;
}

[StructLayout(LayoutKind.Sequential)]
public struct CatbotActionInputRecord {
  public int type;
  public CatbotActionMouseInput mi;
}

[StructLayout(LayoutKind.Sequential)]
public struct CatbotActionMouseInput {
  public int dx;
  public int dy;
  public uint mouseData;
  public uint dwFlags;
  public uint time;
  public UIntPtr dwExtraInfo;
}
"@

[void] [CatbotActionInput]::SetProcessDPIAware()

function Focus-CatbotTarget([IntPtr] $Handle, [bool] $Strict) {
  if ($Handle -eq [IntPtr]::Zero -or -not [CatbotActionInput]::IsWindow($Handle)) {
    throw "The play-mode target window is no longer available."
  }
  [void] [CatbotActionInput]::SetForegroundWindow($Handle)
  Start-Sleep -Milliseconds ([Math]::Max(30, [int] $ActionArgs.focusDelayMs))
  $foreground = [CatbotActionInput]::GetForegroundWindow()
  $matched = $foreground.ToInt64() -eq $Handle.ToInt64()
  if ($Strict -and -not $matched) {
    throw "The play-mode target window could not be focused safely."
  }
  return $matched
}

function Press-CatbotKey([int] $Vk, [int] $HoldMs) {
  [CatbotActionInput]::keybd_event([byte] $Vk, 0, 0, [UIntPtr]::Zero)
  Start-Sleep -Milliseconds ([Math]::Max(20, $HoldMs))
  [CatbotActionInput]::keybd_event([byte] $Vk, 0, 2, [UIntPtr]::Zero)
}

function Escape-CatbotSendKeys([string] $Text) {
  $builder = New-Object System.Text.StringBuilder
  foreach ($char in $Text.ToCharArray()) {
    $value = [string] $char
    switch ($value) {
      "\`r" { break }
      "\`n" { [void] $builder.Append("{ENTER}"); break }
      "\`t" { [void] $builder.Append("{TAB}"); break }
      "+" { [void] $builder.Append("{+}"); break }
      "^" { [void] $builder.Append("{^}"); break }
      "%" { [void] $builder.Append("{%}"); break }
      "~" { [void] $builder.Append("{~}"); break }
      "(" { [void] $builder.Append("{(}"); break }
      ")" { [void] $builder.Append("{)}"); break }
      "[" { [void] $builder.Append("{[}"); break }
      "]" { [void] $builder.Append("{]}"); break }
      "{" { [void] $builder.Append("{{}"); break }
      "}" { [void] $builder.Append("{}}"); break }
      default { [void] $builder.Append($value) }
    }
  }
  return $builder.ToString()
}

function Get-CatbotCursorPoint() {
  $point = New-Object CatbotActionPoint
  if (-not [CatbotActionInput]::GetCursorPos([ref] $point)) {
    throw "Could not read the current mouse cursor position."
  }
  return $point
}

function Convert-CatbotAbsoluteMouseCoordinate([int] $Value, [int] $Origin, [int] $Size) {
  return [Math]::Max(0, [Math]::Min(65535, [int] [Math]::Round((($Value - $Origin) * 65535.0) / [Math]::Max(1, $Size - 1))))
}

function Move-CatbotCursor([int] $X, [int] $Y) {
  $setCursorOk = [CatbotActionInput]::SetCursorPos($X, $Y)
  Start-Sleep -Milliseconds ([Math]::Max(20, [int] $ActionArgs.moveDelayMs))
  $point = Get-CatbotCursorPoint
  $absoluteMoveUsed = $false
  $warning = ""
  if ([Math]::Abs($point.X - $X) -gt 2 -or [Math]::Abs($point.Y - $Y) -gt 2) {
    $left = [CatbotActionInput]::GetSystemMetrics(76)
    $top = [CatbotActionInput]::GetSystemMetrics(77)
    $width = [CatbotActionInput]::GetSystemMetrics(78)
    $height = [CatbotActionInput]::GetSystemMetrics(79)
    $absoluteX = Convert-CatbotAbsoluteMouseCoordinate $X $left $width
    $absoluteY = Convert-CatbotAbsoluteMouseCoordinate $Y $top $height
    $sent = [CatbotActionInput]::SendMouse(([CatbotActionInput]::MouseMove -bor [CatbotActionInput]::MouseAbsolute -bor [CatbotActionInput]::MouseVirtualDesk), $absoluteX, $absoluteY)
    if ($sent -ne 1) {
      $warning = "Windows SendInput absolute cursor move returned $sent."
    } else {
      $absoluteMoveUsed = $true
      Start-Sleep -Milliseconds ([Math]::Max(20, [int] $ActionArgs.moveDelayMs))
      $point = Get-CatbotCursorPoint
    }
  }
  $verified = ([Math]::Abs($point.X - $X) -le 3 -and [Math]::Abs($point.Y - $Y) -le 3)
  if (-not $verified) {
    $mismatch = "Cursor verification mismatch. Requested ($X, $Y), final ($($point.X), $($point.Y))."
    if ($warning) {
      $warning = "$warning $mismatch"
    } else {
      $warning = $mismatch
    }
  }
  return [PSCustomObject]@{
    setCursorOk = $setCursorOk
    absoluteMoveUsed = $absoluteMoveUsed
    verified = $verified
    requestedX = $X
    requestedY = $Y
    x = $point.X
    y = $point.Y
    warning = $warning
  }
}

function Send-CatbotMouseButton([uint32] $Down, [uint32] $Up, [int] $HoldMs) {
  if ([CatbotActionInput]::SendMouse($Down, 0, 0) -ne 1) {
    throw "Windows SendInput could not send mouse button down."
  }
  Start-Sleep -Milliseconds ([Math]::Max(30, $HoldMs))
  if ([CatbotActionInput]::SendMouse($Up, 0, 0) -ne 1) {
    throw "Windows SendInput could not send mouse button up."
  }
}

$targetHwnd = [IntPtr] ([Int64] $ActionArgs.hwnd)
$kind = ([string] $ActionArgs.kind).ToLowerInvariant()
$focusMatched = $false
$cursorResult = $null

if ($kind -eq "mouse") {
  $focusMatched = Focus-CatbotTarget $targetHwnd $false
  $x = [int] $ActionArgs.x
  $y = [int] $ActionArgs.y
  $cursorResult = Move-CatbotCursor $x $y
  $button = ([string] $ActionArgs.button).ToLowerInvariant()
  $down = [CatbotActionInput]::MouseLeftDown
  $up = [CatbotActionInput]::MouseLeftUp
  if ($button -eq "right") {
    $down = [CatbotActionInput]::MouseRightDown
    $up = [CatbotActionInput]::MouseRightUp
  } elseif ($button -eq "middle") {
    $down = [CatbotActionInput]::MouseMiddleDown
    $up = [CatbotActionInput]::MouseMiddleUp
  }
  $clicks = [Math]::Max(0, [Math]::Min(3, [int] $ActionArgs.clicks))
  for ($index = 0; $index -lt $clicks; $index += 1) {
    [void] [CatbotActionInput]::SetCursorPos($x, $y)
    Start-Sleep -Milliseconds 10
    Send-CatbotMouseButton $down $up ([Math]::Max(30, [int] $ActionArgs.holdMs))
    if ($index + 1 -lt $clicks) {
      Start-Sleep -Milliseconds 90
    }
  }
} elseif ($kind -eq "key") {
  $focusMatched = Focus-CatbotTarget $targetHwnd $true
  $key = ([string] $ActionArgs.key).Trim().ToLowerInvariant()
  $vkMap = @{
    "up" = 0x26; "arrowup" = 0x26
    "down" = 0x28; "arrowdown" = 0x28
    "left" = 0x25; "arrowleft" = 0x25
    "right" = 0x27; "arrowright" = 0x27
    "space" = 0x20; "spacebar" = 0x20
    "enter" = 0x0D; "return" = 0x0D
    "escape" = 0x1B; "esc" = 0x1B
    "tab" = 0x09
    "backspace" = 0x08
    "delete" = 0x2E
    "shift" = 0x10
    "ctrl" = 0x11; "control" = 0x11
    "alt" = 0x12
    "w" = 0x57; "a" = 0x41; "s" = 0x53; "d" = 0x44
    "q" = 0x51; "e" = 0x45; "r" = 0x52; "f" = 0x46
    "z" = 0x5A; "x" = 0x58; "c" = 0x43; "v" = 0x56
    "0" = 0x30; "1" = 0x31; "2" = 0x32; "3" = 0x33; "4" = 0x34
    "5" = 0x35; "6" = 0x36; "7" = 0x37; "8" = 0x38; "9" = 0x39
  }
  if (-not $vkMap.ContainsKey($key)) {
    throw "Unsupported action key: $key"
  }
  $repeat = [Math]::Max(1, [Math]::Min(20, [int] $ActionArgs.repeat))
  for ($index = 0; $index -lt $repeat; $index += 1) {
    Press-CatbotKey $vkMap[$key] ([Math]::Max(20, [int] $ActionArgs.holdMs))
    if ($index + 1 -lt $repeat) {
      Start-Sleep -Milliseconds ([Math]::Max(20, [int] $ActionArgs.intervalMs))
    }
  }
} elseif ($kind -eq "type") {
  $focusMatched = Focus-CatbotTarget $targetHwnd $true
  $text = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String([string] $ActionArgs.textBase64))
  if ($text.Length -gt 1000) {
    throw "Typed text is limited to 1000 characters per action."
  }
  [System.Windows.Forms.SendKeys]::SendWait((Escape-CatbotSendKeys $text))
} else {
  throw "Unsupported input action kind: $kind"
}

[PSCustomObject]@{
  success = $true
  kind = $kind
  focusMatched = $focusMatched
  cursor = $cursorResult
} | ConvertTo-Json -Compress -Depth 4
`;

async function getForegroundWindowInfo() {
  return runPowerShellJson(WINDOW_INFO_SCRIPT, {});
}

async function getWindowInfo(hwnd) {
  const normalizedHwnd = normalizeHwnd(hwnd);
  if (!normalizedHwnd) {
    throw new Error("A valid target window handle is required.");
  }
  return runPowerShellJson(WINDOW_INFO_SCRIPT, { hwnd: normalizedHwnd });
}

async function captureWindowWithGrid(options = {}) {
  const grid = normalizeGrid(options.grid || options);
  const outputPath = path.resolve(String(options.outputPath || ""));
  if (!outputPath) {
    throw new Error("Capture output path is required.");
  }
  const result = await runPowerShellJson(CAPTURE_WINDOW_SCRIPT, {
    hwnd: normalizeHwnd(options.hwnd),
    outputPath,
    columns: grid.columns,
    rows: grid.rows,
    overlay: options.overlay !== false,
    format: options.format || "png",
    maxImageWidth: Math.max(0, Math.round(Number(options.maxImageWidth) || 0)),
    jpegQuality: Math.max(35, Math.min(95, Math.round(Number(options.jpegQuality) || 75)))
  }, { timeoutMs: options.timeoutMs || 20000 });
  return {
    ...result,
    grid: normalizeGrid(result.grid || grid),
    outputPath
  };
}

async function sendMouseInput(options = {}) {
  const hwnd = normalizeHwnd(options.hwnd);
  if (!hwnd) {
    throw new Error("A play-mode target window is required before mouse input can run.");
  }
  const x = Math.round(Number(options.x));
  const y = Math.round(Number(options.y));
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error("Mouse input requires finite screen coordinates.");
  }
  const requestedClicks = Number(options.clicks);
  const clicks = Number.isFinite(requestedClicks)
    ? Math.max(0, Math.min(3, Math.round(requestedClicks)))
    : 1;
  return runPowerShellJson(INPUT_SCRIPT, {
    kind: "mouse",
    hwnd,
    x,
    y,
    button: String(options.button || "left"),
    clicks,
    holdMs: Math.max(20, Math.min(1000, Math.round(Number(options.holdMs) || 45))),
    moveDelayMs: Math.max(20, Math.min(1000, Math.round(Number(options.moveDelayMs) || 80))),
    focusDelayMs: Math.max(30, Math.min(1000, Math.round(Number(options.focusDelayMs) || 120))),
    requireActive: options.requireActive === true
  });
}

async function sendKeyInput(options = {}) {
  const hwnd = normalizeHwnd(options.hwnd);
  if (!hwnd) {
    throw new Error("A play-mode target window is required before keyboard input can run.");
  }
  return runPowerShellJson(INPUT_SCRIPT, {
    kind: "key",
    hwnd,
    key: String(options.key || ""),
    repeat: Math.max(1, Math.min(20, Math.round(Number(options.repeat) || 1))),
    holdMs: Math.max(20, Math.min(5000, Math.round(Number(options.holdMs) || 60))),
    intervalMs: Math.max(20, Math.min(5000, Math.round(Number(options.intervalMs) || 80))),
    focusDelayMs: Math.max(30, Math.min(1000, Math.round(Number(options.focusDelayMs) || 120))),
    requireActive: options.requireActive !== false
  });
}

async function typeTextInput(options = {}) {
  const hwnd = normalizeHwnd(options.hwnd);
  if (!hwnd) {
    throw new Error("A play-mode target window is required before typed input can run.");
  }
  const text = String(options.text || "");
  if (!text) {
    throw new Error("Typed input requires text.");
  }
  return runPowerShellJson(INPUT_SCRIPT, {
    kind: "type",
    hwnd,
    textBase64: Buffer.from(text.slice(0, 1000), "utf8").toString("base64"),
    focusDelayMs: Math.max(30, Math.min(1000, Math.round(Number(options.focusDelayMs) || 120))),
    requireActive: options.requireActive !== false
  }, { timeoutMs: 20000 });
}

function parseGridCell(value) {
  const match = String(value || "").trim().toUpperCase().match(/^([A-Z]{1,2})\s*([1-9][0-9]*)$/);
  if (!match) {
    return null;
  }
  const columnIndex = gridColumnIndex(match[1]);
  return {
    columnIndex,
    rowIndex: Number(match[2]) - 1,
    label: `${match[1]}${match[2]}`
  };
}

function gridCellToScreenPoint(cellLabel, capture) {
  const parsed = parseGridCell(cellLabel);
  const rect = capture?.rect || {};
  const grid = normalizeGrid(capture?.grid || {});
  if (!parsed) {
    throw new Error(`Invalid grid cell "${cellLabel}". Use a label like A1, C4, or AA12.`);
  }
  if (parsed.columnIndex < 0 || parsed.columnIndex >= grid.columns || parsed.rowIndex < 0 || parsed.rowIndex >= grid.rows) {
    throw new Error(`Grid cell ${parsed.label} is outside the current ${grid.columns}x${grid.rows} capture.`);
  }
  const x = Math.round(Number(rect.x) + (parsed.columnIndex + 0.5) * (Number(rect.width) / grid.columns));
  const y = Math.round(Number(rect.y) + (parsed.rowIndex + 0.5) * (Number(rect.height) / grid.rows));
  return { x, y, cell: parsed.label };
}

function isFiniteCoordinate(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function getCaptureRect(capture) {
  const rect = capture?.rect || {};
  const x = Number(rect.x);
  const y = Number(rect.y);
  const width = Number(rect.width);
  const height = Number(rect.height);
  if (![x, y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
    throw new Error("A valid play-mode capture is required before coordinate mouse input can run.");
  }
  return {
    x,
    y,
    width,
    height,
    right: Number.isFinite(Number(rect.right)) ? Number(rect.right) : x + width,
    bottom: Number.isFinite(Number(rect.bottom)) ? Number(rect.bottom) : y + height
  };
}

function coordinateToScreenPoint(coordinates = {}, capture) {
  const rawX = isFiniteCoordinate(
    coordinates.x ?? coordinates.screenX ?? coordinates.clientX ?? coordinates.windowX ?? coordinates.imageX
  );
  const rawY = isFiniteCoordinate(
    coordinates.y ?? coordinates.screenY ?? coordinates.clientY ?? coordinates.windowY ?? coordinates.imageY
  );
  if (rawX == null || rawY == null) {
    throw new Error("Mouse input requires either a grid cell or finite x/y coordinates.");
  }

  const rect = getCaptureRect(capture);
  const requestedSpace = String(
    coordinates.coordinateSpace ||
    coordinates.coordinate_space ||
    coordinates.space ||
    ""
  ).trim().toLowerCase();
  const wantsScreenSpace =
    coordinates.screen === true ||
    coordinates.absolute === true ||
    ["screen", "absolute", "desktop"].includes(requestedSpace);
  const wantsWindowSpace =
    coordinates.relative === true ||
    ["window", "client", "image", "capture", "relative"].includes(requestedSpace);
  const looksWindowRelative = rawX >= 0 && rawX <= rect.width && rawY >= 0 && rawY <= rect.height;

  const coordinateSpace = wantsScreenSpace
    ? "screen"
    : wantsWindowSpace || looksWindowRelative
      ? "window"
      : "screen";
  const screenX = coordinateSpace === "window" ? rect.x + rawX : rawX;
  const screenY = coordinateSpace === "window" ? rect.y + rawY : rawY;
  const clampedX = Math.round(Math.max(rect.x, Math.min(rect.right - 1, screenX)));
  const clampedY = Math.round(Math.max(rect.y, Math.min(rect.bottom - 1, screenY)));

  return {
    x: clampedX,
    y: clampedY,
    cell: `${coordinateSpace}:${Math.round(rawX)},${Math.round(rawY)}`,
    coordinateSpace,
    requestedX: Math.round(rawX),
    requestedY: Math.round(rawY)
  };
}

function mouseTargetToScreenPoint(target = {}, capture) {
  const cell = target.cell || target.target || target.gridCell || target.grid_cell;
  if (cell) {
    return gridCellToScreenPoint(cell, capture);
  }
  return coordinateToScreenPoint(target, capture);
}

function readCaptureDataUrl(capturePath) {
  const bytes = fs.readFileSync(capturePath);
  const extension = path.extname(String(capturePath || "")).toLowerCase();
  const mimeType = extension === ".jpg" || extension === ".jpeg" ? "image/jpeg" : "image/png";
  return `data:${mimeType};base64,${bytes.toString("base64")}`;
}

function cleanupOldCaptures(directory, maxAgeMs = 24 * 60 * 60 * 1000) {
  try {
    if (!fs.existsSync(directory)) {
      return;
    }
    const cutoff = Date.now() - maxAgeMs;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (!entry.isFile() || !/^capture-\d+\.(?:png|jpe?g)$/i.test(entry.name)) {
        continue;
      }
      const fullPath = path.join(directory, entry.name);
      const stats = fs.statSync(fullPath);
      if (stats.mtimeMs < cutoff) {
        fs.unlinkSync(fullPath);
      }
    }
  } catch (_) {
    // Best-effort cleanup only.
  }
}

module.exports = {
  DEFAULT_GRID_COLUMNS,
  DEFAULT_GRID_ROWS,
  MAX_GRID_COLUMNS,
  MAX_GRID_ROWS,
  delay,
  normalizeGrid,
  normalizeHwnd,
  getForegroundWindowInfo,
  getWindowInfo,
  captureWindowWithGrid,
  sendMouseInput,
  sendKeyInput,
  typeTextInput,
  gridColumnLabel,
  gridColumnIndex,
  parseGridCell,
  gridCellToScreenPoint,
  coordinateToScreenPoint,
  mouseTargetToScreenPoint,
  readCaptureDataUrl,
  cleanupOldCaptures
};
