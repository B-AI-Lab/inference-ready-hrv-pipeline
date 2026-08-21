$ErrorActionPreference = "Stop"

$root = Join-Path $PSScriptRoot "dist"
$port = 5174
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $port)
$listener.Start()
Write-Host "Serving $root at http://127.0.0.1:$port/"

while ($true) {
  $client = $listener.AcceptTcpClient()
  try {
    $stream = $client.GetStream()
    $reader = [System.IO.StreamReader]::new($stream, [Text.Encoding]::ASCII, $false, 1024, $true)
    $line = $reader.ReadLine()
    while ($reader.Peek() -ge 0) {
      if ([string]::IsNullOrEmpty($reader.ReadLine())) { break }
    }

    $path = "index.html"
    if ($line -match '^GET\s+([^\s]+)') {
      $path = [System.Uri]::UnescapeDataString($matches[1].Split("?")[0].TrimStart("/"))
    }
    if ([string]::IsNullOrWhiteSpace($path)) { $path = "index.html" }

    $full = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($root, $path))
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -or -not [System.IO.File]::Exists($full)) {
      $full = [System.IO.Path]::Combine($root, "index.html")
    }

    $ext = [System.IO.Path]::GetExtension($full).ToLowerInvariant()
    $type = switch ($ext) {
      ".html" { "text/html; charset=utf-8" }
      ".js" { "text/javascript; charset=utf-8" }
      ".css" { "text/css; charset=utf-8" }
      ".jpeg" { "image/jpeg" }
      ".jpg" { "image/jpeg" }
      ".png" { "image/png" }
      default { "application/octet-stream" }
    }

    $bytes = [System.IO.File]::ReadAllBytes($full)
    $header = "HTTP/1.1 200 OK`r`nContent-Type: $type`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-cache`r`nConnection: close`r`n`r`n"
    $headerBytes = [Text.Encoding]::ASCII.GetBytes($header)
    $stream.Write($headerBytes, 0, $headerBytes.Length)
    $stream.Write($bytes, 0, $bytes.Length)
  } catch {
    Write-Host $_
  } finally {
    $client.Close()
  }
}
