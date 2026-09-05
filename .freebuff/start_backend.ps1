$root = 'C:\Users\tejas\OneDrive\Desktop\FinOps'
$py = 'C:\Users\tejas\AppData\Local\Programs\Python\Python310\python.exe'
$p = Start-Process -FilePath $py `
    -ArgumentList '-m', 'uvicorn', 'apps.api.main:app', '--host', '0.0.0.0', '--port', '8000', '--app-dir', '.' `
    -WorkingDirectory $root `
    -RedirectStandardOutput (Join-Path $root '.freebuff\backend2.log') `
    -RedirectStandardError (Join-Path $root '.freebuff\backend2.err.log') `
    -WindowStyle Hidden -PassThru
Write-Output $p.Id
