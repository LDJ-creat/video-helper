Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$out = 'D:\vh-ytdlp-run'
New-Item -ItemType Directory -Force -Path $out | Out-Null

$py = 'D:\video-helper\services\core\.venv\Scripts\python.exe'
$cookie = 'D:\video-helper\www.bilibili.com_cookies.txt'
$url = 'https://www.bilibili.com/video/BV1G4iMBeEWH/?spm_id_from=333.337.search-card.all.click'

& $py -m yt_dlp --ignore-config --no-playlist --no-progress --paths $out -o 'source.%(ext)s' --cookies $cookie $url
Write-Host "RC=$LASTEXITCODE"
Get-ChildItem -Force -Path $out | Select-Object Name, Length | Format-Table -AutoSize
