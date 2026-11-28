# Disposable synthetic archive: import, search, verify, clean up. No network.
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$workdir = Join-Path ([System.IO.Path]::GetTempPath()) ("hb-continuum-quickstart-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workdir | Out-Null

try {
    $archive = Join-Path $workdir 'archive'
    $fixture = Join-Path $workdir 'sample.eml'
    $eml = @'
From: Ada Example <ada@example.invalid>
To: Grace Example <grace@example.invalid>
Subject: Fictional invoice for March
Date: Tue, 14 Mar 2023 09:15:00 +0000
Message-ID: <quickstart-0001@example.invalid>
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

This message is entirely fictional and exists only for the quickstart.

The invoice number is QS-1042 and it is attached to a project that never
existed. Ada Example signed it on a made-up planet.
'@
    Set-Content -Path $fixture -Value $eml -Encoding utf8

    Push-Location $repoRoot
    try {
        Write-Host '1. Import a synthetic EML file'
        $imported = & python dispatch.py --archive $archive import $fixture 2>&1 | Out-String
        Write-Host $imported.Trim()
        $hashId = ($imported.Trim() -split "`r?`n")[-1]

        Write-Host ''
        Write-Host '2. Import the same file again (deduplication, no new record)'
        $again = & python dispatch.py --archive $archive import $fixture 2>&1 | Out-String
        Write-Host $again.Trim()
        if ($again -notmatch 'existing') {
            throw 'quickstart: FAILED (duplicate was not detected)'
        }

        Write-Host ''
        Write-Host '3. Search the archive'
        $results = & python dispatch.py --archive $archive search invoice | Out-String
        Write-Host $results.Trim()
        if ($results -notmatch [regex]::Escape($hashId)) {
            throw 'quickstart: FAILED (search did not return the imported record)'
        }

        Write-Host ''
        Write-Host '4. Verify stored bytes against their hashes'
        $verification = (& python dispatch.py --archive $archive verify | Out-String).Trim()
        Write-Host $verification
        if ($verification -ne '[]') {
            throw 'quickstart: FAILED (verification reported mismatches)'
        }

        Write-Host ''
        Write-Host 'quickstart: OK (temporary archive removed)'
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item -Recurse -Force $workdir -ErrorAction SilentlyContinue
}
