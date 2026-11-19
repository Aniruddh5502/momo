# PowerShell Command Reference (for bash-tool use)

## Invocation from bash

- `pwsh -NoProfile -Command "<command>"` — runs one command and exits
- `pwsh -NoProfile -File script.ps1` — runs a script file
- `pwsh -NoProfile -EncodedCommand <base64>` — runs a command without quoting problems
- `-NoProfile` — skips the user profile, so output is clean and fast
- `-NonInteractive` — fails instead of prompting
- `-ExecutionPolicy Bypass` — allows scripts to run without changing policy
- `-Command -` — reads the command from stdin
- Note: `pwsh` is PowerShell 7+. On systems with only Windows PowerShell 5.1, use `powershell` instead.

## Navigation and files

Get-ChildItem (gci, ls, dir) — lists files and folders
- `-Path <p>` — folder to list
- `-Recurse` — include subfolders
- `-Filter <pattern>` — fast wildcard filter (e.g. `*.log`)
- `-Include` / `-Exclude <pattern>` — filter by name, works with `-Recurse`
- `-File` / `-Directory` — show only files or only folders
- `-Force` — include hidden and system items

Get-Content (gc, cat, type) — reads a file as lines
- `-Path <p>` — file to read
- `-TotalCount <n>` (`-First`) — first n lines
- `-Tail <n>` — last n lines
- `-Wait` — follow a file as it grows
- `-Raw` — read the whole file as one string
- `-Encoding <enc>` — set encoding (utf8, ascii, unicode)

Set-Content (sc) — writes a file, replacing it
- `-Path <p>` — target file
- `-Value <text>` — content to write
- `-Encoding <enc>` — output encoding

Add-Content (ac) — appends to a file
- `-Path <p>` — target file
- `-Value <text>` — text to append

Copy-Item (cp, copy) — copies files or folders
- `-Recurse` — copy folder contents
- `-Force` — overwrite existing

Move-Item (mv, move) — moves or renames
Rename-Item (ren) — renames in place
- `-NewName <name>` — new name

Remove-Item (rm, del, rmdir) — deletes files or folders
- `-Recurse` — delete folder contents
- `-Force` — include hidden and read-only items
- `-WhatIf` — show what would be deleted, without deleting

New-Item (ni) — creates files or folders
- `-ItemType File|Directory` — what to create
- `-Force` — create parent folders as needed

Test-Path — checks whether a path exists
- `-PathType Leaf|Container` — file or folder check

Resolve-Path — expands a path to its full form
Set-Location (cd, sl) — changes folder
Get-Location (pwd) — prints the current folder
Push-Location / Pop-Location (pushd / popd) — stack-based folder changes
Get-Item / Get-ItemProperty — shows item details (size, dates, attributes)
Get-FileHash — hash of a file
- `-Algorithm SHA256|MD5|SHA1` — hash type

## Searching text

Select-String (sls) — regex search across files, like grep
- `-Path <p>` — files to search (wildcards allowed)
- `-Pattern <regex>` — what to find
- `-Recurse` — search subfolders (pair with `-Path` or `Get-ChildItem`)
- `-SimpleMatch` — treat the pattern as literal text
- `-CaseSensitive` — match case exactly
- `-Context <before>,<after>` — show surrounding lines
- `-List` — return only filenames with matches
- `-Quiet` — return true/false only

Where-Object (where, ?) — filters objects
- Example: `Get-Process | Where-Object CPU -gt 10`
- Operators: `-eq`, `-ne`, `-gt`, `-lt`, `-like`, `-match`, `-contains`

## Objects and pipeline

Select-Object (select) — picks properties or first/last items
- `-Property <names>` — columns to keep
- `-First <n>` / `-Last <n>` — first or last n items
- `-Unique` — remove duplicates

ForEach-Object (foreach, %) — runs a block per item
Sort-Object (sort) — sorts items
- `-Property <name>` — sort key
- `-Descending` — reverse order

Group-Object (group) — groups items by a property
- `-Property <name>` — grouping key
- `-NoElement` — count only

Measure-Object (measure) — counts, sums, averages
- `-Sum` / `-Average` / `-Maximum` / `-Minimum` — statistics
- `-Property <name>` — field to measure

Compare-Object (diff) — compares two sets of items
Format-Table (ft) — prints as a table
- `-AutoSize` — fit column widths
- `-Wrap` — wrap long values

Format-List (fl) — prints every property as a list
Out-String — converts output to plain text
ConvertTo-Json — objects to JSON
- `-Depth <n>` — nesting depth
- `-Compress` — single line

ConvertFrom-Json — JSON text to objects
ConvertTo-Csv / ConvertFrom-Csv — CSV conversion
Import-Csv — reads a CSV file as objects
Export-Csv — writes objects to CSV
- `-NoTypeInformation` — omit the type header line

ConvertTo-Html — objects to an HTML table
Out-File — writes output to a file
- `-FilePath <p>` — target file
- `-Append` — add instead of overwrite

Tee-Object — writes output to a file and passes it on

## Processes and services

Get-Process (gps, ps) — lists running processes
- `-Name <name>` — filter by process name
- `-Id <pid>` — filter by process ID

Stop-Process (kill, spps) — ends a process
- `-Id <pid>` / `-Name <name>` — target
- `-Force` — end without confirmation

Start-Process (start, saps) — starts a program
- `-FilePath <exe>` — program to run
- `-ArgumentList <args>` — arguments
- `-Wait` — wait for it to finish
- `-NoNewWindow` — run in the same console
- `-RedirectStandardOutput <file>` — capture output
- `-Verb RunAs` — request elevation

Get-Service (gsv) — lists services
- `-Name <name>` — filter by service name
- `-Status Running|Stopped` — filter by state

Start-Service / Stop-Service / Restart-Service — controls a service
Set-Service — changes startup type or state
- `-StartupType Automatic|Manual|Disabled`

Get-CimInstance — queries system data classes
- `-ClassName <class>` — e.g. Win32_OperatingSystem, Win32_LogicalDisk, Win32_Processor
- `-Filter "<condition>"` — WQL filter

Get-ComputerInfo — summary of OS, hardware, and BIOS
Get-WinEvent — reads event logs (preferred over Get-EventLog)
- `-LogName System|Application|Security` — which log
- `-MaxEvents <n>` — limit results
- `-FilterHashtable @{LogName=...; Level=...; StartTime=...}` — precise filters

Get-Counter — performance counter values
- `-Counter "\Processor(_Total)\% Processor Time"` — counter path
- `-SampleInterval <s> -MaxSamples <n>`

## System and environment

Get-Date — current date and time
- `-Format <fmt>` — e.g. `"yyyy-MM-dd HH:mm:ss"`
- `-UFormat <fmt>` — Unix-style formatting

Get-Command — finds commands
- `-Name <pattern>` — search by name
- `-CommandType Cmdlet|Function|Application`

Get-Help <cmd> — documentation for a command
- `-Examples` — show examples
- `-Full` — all details
- `-Online` — open the online docs

Get-Member (gm) — lists properties and methods of an object
- `-MemberType Property|Method`

$env:NAME — environment variable (read or set)
Get-ChildItem Env: — lists all environment variables
[Environment]::SetEnvironmentVariable(name, value, scope) — persistent change
- `-Scope User|Machine|Process`

Get-Variable / Set-Variable — shell variables
Get-Alias — alias lookup
Set-Alias / New-Alias — creates an alias

Invoke-WebRequest (iwr) — HTTP request
- `-Uri <url>` — target
- `-Method GET|POST|PUT|DELETE` — HTTP method
- `-Body <data>` — request body
- `-Headers @{...}` — request headers
- `-OutFile <file>` — save response to a file
- `-UseBasicParsing` — avoid the Internet Explorer engine (needed on 5.1)

Invoke-RestMethod (irm) — HTTP request, parses JSON or XML automatically
- `-Uri <url>` — target
- `-Method <verb>` — HTTP method
- `-Body <json>` — request body
- `-ContentType "application/json"` — body type
- `-Headers @{...}` — auth or other headers

Test-Connection (ping) — ICMP ping
- `-ComputerName <host>` — target
- `-Count <n>` — number of pings

Test-NetConnection — tests a TCP port
- `-ComputerName <host> -Port <n>`

Get-NetIPAddress — IP configuration
Get-NetAdapter — network adapters
Resolve-DnsName — DNS lookup
- `-Name <host> -Type A|AAAA|MX|TXT`

## Scripting and control flow

- `$var = value` — assigns a variable
- `@( )` — array; `@{ }` — hashtable
- `if` / `elseif` / `else` — conditionals
- `foreach ($x in $list) { }` — loop over items
- `for ($i=0; $i -lt 10; $i++) { }` — counted loop
- `while` / `do..while` / `do..until` — conditional loops
- `switch ($value) { "a" { } default { } }` — multi-branch
- `try { } catch { } finally { }` — error handling
- `throw "message"` — raises an error
- `$ErrorActionPreference = "Stop"` — makes non-terminating errors stop the script
- `-ErrorAction Stop` — per-command version of the same
- `$LASTEXITCODE` — exit code of the last native program
- `exit <code>` — ends the script with a code
- `$?` — whether the last command succeeded
- `function Name { param($a) ... }` — defines a function
- `param( [string]$Path )` — script parameters
- `$PSScriptRoot` — folder the script is in
- `$args` — unbound arguments
- `Read-Host` — prompts for input (avoid in non-interactive runs)
- `Start-Sleep -Seconds <n>` — pauses
- `Write-Output` (echo) — writes to the pipeline
- `Write-Host` — writes to the console only (not captured by the pipeline)
- `Write-Error` / `Write-Warning` / `Write-Verbose` — messages on their own streams
- `-Verbose` on any cmdlet — shows verbose output

## Strings and regex

- `"text $var"` — expands variables in double quotes
- `'text'` — literal, no expansion
- `@" ... "@` — here-string for multi-line text
- `-replace <regex>, <replacement>` — regex replace
- `-match <regex>` — tests a match; fills `$Matches`
- `-split <regex>` — splits on a regex
- `-join <sep>` — joins an array
- `-f` format — e.g. `"{0}: {1}" -f $a, $b`
- `[regex]::Matches(text, pattern)` — all matches
- `[System.IO.File]::ReadAllText(path)` — fast full-file read
- `[System.IO.File]::WriteAllText(path, text)` — fast full-file write

## Archives

Compress-Archive — creates a zip
- `-Path <items> -DestinationPath <zip>`
- `-Update` — add to an existing zip

Expand-Archive — extracts a zip
- `-Path <zip> -DestinationPath <folder>`
- `-Force` — overwrite existing

## Packages and tools

- `winget install <id>` — installs an app
- `winget search <name>` — finds packages
- `winget upgrade --all` — updates installed packages
- `choco install <name>` — Chocolatey install (if present)
- `scoop install <name>` — Scoop install (if present)
- `Get-Module -ListAvailable` — installed PowerShell modules
- `Install-Module <name> -Scope CurrentUser` — installs a module
- `Import-Module <name>` — loads a module

## Notes for the agent

- Run `pwsh -NoProfile -Command "..."` from bash and wrap the command in double quotes. Escape `$` as `\$`, or put the PowerShell code in single quotes.
- Prefer `-WhatIf` before any `Remove-Item` or `Stop-Process`.
- Use `-Encoding utf8` when writing files, since Windows PowerShell 5.1 and 7 default differently.
- Pipe to `ConvertTo-Json` or `Export-Csv` when the output will be parsed later.
- Check `$LASTEXITCODE` after native programs such as git or python.
- `curl` is an alias for Invoke-WebRequest only in Windows PowerShell 5.1. In pwsh 7 it is the real curl.exe, so use `iwr` or `irm` for consistent behavior.



===================================================================
# PowerShell Quick Reference

Run from bash: `pwsh -NoProfile -Command "<command>"`

* find files: `Get-ChildItem -Path <folder> -Recurse -Filter <pattern>`
* list files and folders, recursively: `Get-ChildItem -Path <folder> -Recurse`
* list files and folders, normally: `Get-ChildItem -Path <folder>`
* search specific types of files: `Get-ChildItem -Path <folder> -Recurse -Include *.<ext>`
* search text inside files: `Select-String -Path <folder>\*.<ext> -Pattern <regex> -Recurse`
* delete files/folders: `Remove-Item -Path <path> -Recurse -Force` (add `-WhatIf` first to preview)
* read a file: `Get-Content -Path <file>`
* write a file: `Set-Content -Path <file> -Value <text> -Encoding utf8`
* append to a file: `Add-Content -Path <file> -Value <text>`
* copy files/folders: `Copy-Item -Path <src> -Destination <dst> -Recurse`
* move or rename: `Move-Item -Path <src> -Destination <dst>`
* check a path exists: `Test-Path -Path <path>`
* list running processes: `Get-Process`
* stop a process: `Stop-Process -Name <name>`
* make a folder: `New-Item -ItemType Directory -Path <folder> -Force`
* check exit code of a native program: `$LASTEXITCODE`