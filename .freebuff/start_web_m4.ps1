$web = 'C:\Users\tejas\AppData\Local\Temp\finops-preview-web-m4'
$p = Start-Process -FilePath 'npm.cmd' `
    -ArgumentList 'run', 'dev', '--', '-p', '3003' `
    -WorkingDirectory $web `
    -RedirectStandardOutput 'C:\Users\tejas\OneDrive\Desktop\FinOps\.freebuff\m4web.log' `
    -RedirectStandardError 'C:\Users\tejas\OneDrive\Desktop\FinOps\.freebuff\m4web.err.log' `
    -WindowStyle Hidden -PassThru
Write-Output $p.Id
