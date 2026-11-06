param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$target = Join-Path $repoRoot 'dashboard\templates\sales_opportunity_template.xlsx'
$temporary = "$target.new"
$source = (Resolve-Path -LiteralPath $SourcePath).Path
if ($source -eq $target) { throw 'Source and output must be different files.' }

$removed = @(
    'xl/worksheets/sheet2.xml', 'xl/worksheets/sheet3.xml',
    'xl/worksheets/_rels/sheet1.xml.rels', 'xl/worksheets/_rels/sheet2.xml.rels',
    'xl/worksheets/_rels/sheet3.xml.rels',
    'xl/drawings/drawing1.xml', 'xl/drawings/drawing2.xml', 'xl/drawings/drawing3.xml',
    'xl/sharedStrings.xml', 'xl/persons/person.xml'
)
$removedParts = @($removed | ForEach-Object { '/' + $_ })

function Read-Xml($entry) {
    $doc = [System.Xml.XmlDocument]::new()
    $doc.PreserveWhitespace = $true
    $stream = $entry.Open()
    try { $doc.Load($stream) } finally { $stream.Dispose() }
    return $doc
}

function Write-Xml($entry, $doc) {
    $stream = $entry.Open()
    try { $doc.Save($stream) } finally { $stream.Dispose() }
}

function Put-Label($doc, $ns, [string]$address, [string]$value) {
    $cell = $doc.SelectSingleNode("//x:c[@r='$address']", $ns)
    if ($null -eq $cell) { throw "Required template cell $address is missing." }
    $cell.SetAttribute('t', 'inlineStr')
    $inline = $doc.CreateElement('is', $ns.LookupNamespace('x'))
    $text = $doc.CreateElement('t', $ns.LookupNamespace('x'))
    $text.InnerText = $value
    [void]$inline.AppendChild($text)
    [void]$cell.AppendChild($inline)
}

function Put-Formula($doc, $ns, [string]$address, [string]$formula) {
    $cell = $doc.SelectSingleNode("//x:c[@r='$address']", $ns)
    if ($null -eq $cell) { throw "Required template formula cell $address is missing." }
    $cell.RemoveAttribute('t')
    $f = $cell.SelectSingleNode('x:f', $ns)
    if ($null -eq $f) {
        $f = $doc.CreateElement('f', $ns.LookupNamespace('x'))
        [void]$cell.AppendChild($f)
    }
    $f.InnerText = $formula
}

$input = [System.IO.Compression.ZipFile]::OpenRead($source)
try {
    if (Test-Path -LiteralPath $temporary) { throw "Temporary output already exists: $temporary" }
    $output = [System.IO.Compression.ZipFile]::Open($temporary, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($item in $input.Entries) {
            if ($item.FullName -in $removed) { continue }
            $new = $output.CreateEntry($item.FullName, [System.IO.Compression.CompressionLevel]::Optimal)
            if ($item.FullName -eq 'xl/workbook.xml') {
                $doc = Read-Xml $item
                $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
                $ns.AddNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
                $sheets = @($doc.SelectNodes('//x:sheets/x:sheet', $ns))
                if ($sheets.Count -lt 1) { throw 'No sales sheet in source workbook.' }
                $sheets[0].SetAttribute('name', 'Sales Brief')
                foreach ($sheet in $sheets | Select-Object -Skip 1) { [void]$sheet.ParentNode.RemoveChild($sheet) }
                Write-Xml $new $doc
            } elseif ($item.FullName -eq 'xl/_rels/workbook.xml.rels') {
                $doc = Read-Xml $item
                $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
                $ns.AddNamespace('r', 'http://schemas.openxmlformats.org/package/2006/relationships')
                foreach ($rel in @($doc.SelectNodes('//r:Relationship', $ns))) {
                    $resolved = 'xl/' + $rel.GetAttribute('Target').TrimStart('/')
                    if ($resolved -in $removed) { [void]$rel.ParentNode.RemoveChild($rel) }
                }
                Write-Xml $new $doc
            } elseif ($item.FullName -eq '[Content_Types].xml') {
                $doc = Read-Xml $item
                $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
                $ns.AddNamespace('c', 'http://schemas.openxmlformats.org/package/2006/content-types')
                foreach ($override in @($doc.SelectNodes('//c:Override', $ns))) {
                    if ($override.GetAttribute('PartName') -in $removedParts) {
                        [void]$override.ParentNode.RemoveChild($override)
                    }
                }
                Write-Xml $new $doc
            } elseif ($item.FullName -eq 'xl/worksheets/sheet1.xml') {
                $doc = Read-Xml $item
                $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
                $ns.AddNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
                foreach ($cell in @($doc.SelectNodes('//x:sheetData/x:row/x:c', $ns))) {
                    foreach ($child in @($cell.ChildNodes)) { [void]$cell.RemoveChild($child) }
                    $cell.RemoveAttribute('t')
                }
                foreach ($drawing in @($doc.SelectNodes('//x:drawing | //x:legacyDrawing', $ns))) {
                    [void]$drawing.ParentNode.RemoveChild($drawing)
                }
                $labels = @{
                    B2 = 'FORGE INTERNAL OPPORTUNITY ASSESSMENT'; B3 = 'DRAFT - INTERNAL POC ONLY'
                    B5 = 'Opportunity Amount'; D5 = 'Sales Stage'; F5 = 'Expected Signature'; H5 = 'Duration'
                    B9 = 'Serial ID'; B10 = 'Opportunity Name'; B11 = 'Sales Stage'; B12 = 'Client Name'; B13 = 'Opportunity Amount'
                    D9 = 'Assigned To'; D10 = 'Identified By'; D11 = 'Line Item Owners'; D12 = 'Deal Type'; D13 = 'Pricing Model'
                    F9 = 'Customer Key Contact 1'; H9 = 'Designation 1'; F10 = 'Customer Key Contact 2'; H10 = 'Designation 2'
                    F11 = 'Primary Email'; H11 = 'Stakeholder Dept'; F12 = 'Expected Signature Date'; H12 = 'Target Quarter'
                    F13 = 'Duration'; H13 = 'Contract Term'
                }
                foreach ($address in $labels.Keys) { Put-Label $doc $ns $address $labels[$address] }
                $formulas = @{
                    B6 = 'IF(C13="","",C13)'; D6 = 'IF(C11="","",C11)'; F6 = 'IF(G12="","",G12)'
                    H6 = 'IF(G13="","",G13)'; B30 = 'IF(G12="","",G12)'; F30 = 'IF(G13="","",G13)'
                }
                foreach ($address in $formulas.Keys) { Put-Formula $doc $ns $address $formulas[$address] }
                foreach ($validation in @($doc.SelectNodes('//x:dataValidation', $ns))) {
                    $formula1 = $validation.SelectSingleNode('x:formula1', $ns)
                    if ($null -ne $formula1) { $formula1.InnerText = '"Identified,Noticed,Qualified,Validated,Won,Lost"' }
                }
                Write-Xml $new $doc
            } else {
                $readStream = $item.Open()
                $writeStream = $new.Open()
                try { $readStream.CopyTo($writeStream) } finally { $readStream.Dispose(); $writeStream.Dispose() }
            }
        }
    } finally { $output.Dispose() }
} finally { $input.Dispose() }

$check = [System.IO.Compression.ZipFile]::OpenRead($temporary)
try {
    if ($null -eq $check.GetEntry('xl/worksheets/sheet1.xml') -or
        $null -eq $check.GetEntry('xl/workbook.xml')) { throw 'Sanitized workbook is incomplete.' }
    $entry = $check.GetEntry('xl/workbook.xml')
    $doc = Read-Xml $entry
    $ns = [System.Xml.XmlNamespaceManager]::new($doc.NameTable)
    $ns.AddNamespace('x', 'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
    $sheets = @($doc.SelectNodes('//x:sheets/x:sheet', $ns))
    if ($sheets.Count -ne 1 -or $sheets[0].GetAttribute('name') -ne 'Sales Brief') {
        throw 'Sanitized workbook does not have exactly one Sales Brief sheet.'
    }
} finally { $check.Dispose() }

Move-Item -LiteralPath $temporary -Destination $target -Force
Write-Output "Created sanitized blank sales template: $target"
