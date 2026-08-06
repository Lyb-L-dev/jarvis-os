param(
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ApiBase = "http://127.0.0.1:8000/api/v1"
$RuntimeDirectory = Join-Path $ProjectRoot ".runtime"
$StatePath = Join-Path $RuntimeDirectory "demo-data.json"

function Invoke-JarvisJson {
    param(
        [ValidateSet("GET", "POST", "PATCH", "DELETE")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null
    )

    $Parameters = @{
        Uri = "$ApiBase$Path"
        Method = $Method
        UseBasicParsing = $true
        TimeoutSec = 30
    }
    if ($null -ne $Body) {
        $Parameters.ContentType = "application/json; charset=utf-8"
        $Parameters.Body = $Body | ConvertTo-Json -Depth 12 -Compress
    }
    $Response = Invoke-WebRequest @Parameters
    if ($Response.StatusCode -eq 204 -or [string]::IsNullOrWhiteSpace($Response.Content)) {
        return $null
    }
    return $Response.Content | ConvertFrom-Json
}

function Save-State {
    param([System.Collections.IDictionary]$State)

    New-Item -ItemType Directory -Path $RuntimeDirectory -Force | Out-Null
    [System.IO.File]::WriteAllText(
        $StatePath,
        ($State | ConvertTo-Json -Depth 8),
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Remove-DemoRecord {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    try {
        Invoke-JarvisJson -Method DELETE -Path $Path | Out-Null
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 404) {
            throw
        }
    }
}

Invoke-WebRequest `
    -Uri "$ApiBase/health/live" `
    -UseBasicParsing `
    -TimeoutSec 10 | Out-Null

if ($Remove) {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        Write-Output "No active Jarvis demo data set was found."
        exit 0
    }
    $State = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 |
        ConvertFrom-Json

    Remove-DemoRecord -Path "/investment/assets/$($State.asset_id)"
    Remove-DemoRecord -Path "/intelligence/items/$($State.news_id)"
    Remove-DemoRecord -Path "/memories/$($State.memory_id)"
    foreach ($TaskId in @($State.task_ids)) {
        Remove-DemoRecord -Path "/tasks/$TaskId"
    }
    Remove-DemoRecord -Path "/goals/$($State.goal_id)"
    Remove-Item -LiteralPath $StatePath -Force
    Write-Output "Jarvis demo data was removed. Original personal data was not changed."
    exit 0
}

if (Test-Path -LiteralPath $StatePath) {
    throw "Demo data already exists. Run scripts\demo-data.ps1 -Remove first."
}

$Today = Get-Date -Format "yyyy-MM-dd"
$Marker = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$State = [ordered]@{
    created_at = (Get-Date).ToString("o")
    goal_id = $null
    task_ids = @()
    memory_id = $null
    news_id = $null
    asset_id = $null
}
Save-State -State $State

try {
    $Goal = Invoke-JarvisJson -Method POST -Path "/goals" -Body @{
        title = "[DEMO] Build a personal AI operating system"
        description = "Fictional sample goal for showing the goal and task loop."
        area = "technology"
    }
    $State.goal_id = $Goal.id
    Save-State -State $State

    Invoke-JarvisJson -Method POST -Path "/goals/$($Goal.id)/milestones" -Body @{
        title = "Complete one verifiable weekly iteration"
        description = "Fictional milestone with no private information."
        order_index = 1
    } | Out-Null

    $CompletedTask = Invoke-JarvisJson -Method POST -Path "/tasks" -Body @{
        title = "[DEMO] Check automatic backup status"
        description = "Open Settings and confirm that a recovery point is verified."
        area = "technology"
        goal_id = $Goal.id
        priority = 5
        planned_date = $Today
        estimated_minutes = 45
        source_type = "demo"
    }
    $State.task_ids += $CompletedTask.id
    Save-State -State $State
    Invoke-JarvisJson `
        -Method POST `
        -Path "/tasks/$($CompletedTask.id)/start" `
        -Body @{} | Out-Null
    Invoke-JarvisJson `
        -Method POST `
        -Path "/tasks/$($CompletedTask.id)/complete" `
        -Body @{
            actual_minutes = 45
            completion_evidence = "Demo evidence: recovery verification is visible."
        } | Out-Null

    $TodoTask = Invoke-JarvisJson -Method POST -Path "/tasks" -Body @{
        title = "[DEMO] Complete one English review"
        description = "Sample pending task; it does not create a voice reminder."
        area = "english"
        goal_id = $Goal.id
        priority = 3
        planned_date = $Today
        estimated_minutes = 30
        source_type = "demo"
    }
    $State.task_ids += $TodoTask.id
    Save-State -State $State

    $Memory = Invoke-JarvisJson -Method POST -Path "/memories" -Body @{
        memory_type = "preference"
        content = "Demo preference: complete the most important growth task first."
        importance = 4
        cloud_allowed = $false
    }
    $State.memory_id = $Memory.id
    Save-State -State $State

    $News = Invoke-JarvisJson -Method POST -Path "/intelligence/items/manual" -Body @{
        title = "[DEMO] Local-first personal AI system completes a stability upgrade"
        url = "https://example.com/jarvis-demo-$Marker"
        source_name = "Jarvis Demo Source"
        source_excerpt = "Fictional demo fact: the system added backups, restore verification, and local fallback."
        category = "technology"
        language = "zh-CN"
    }
    $State.news_id = $News.id
    Save-State -State $State

    $Asset = Invoke-JarvisJson -Method POST -Path "/investment/assets" -Body @{
        name = "Jarvis Demo Asset"
        symbol = "JARVISDEMO"
        market = "DEMO"
        asset_type = "stock"
        currency = "CNY"
        latest_price = 12
        latest_price_date = $Today
        notes = "Fictional sample asset; it is not a real holding."
    }
    $State.asset_id = $Asset.id
    Save-State -State $State

    Invoke-JarvisJson -Method POST -Path "/investment/positions" -Body @{
        asset_id = $Asset.id
        quantity = 100
        average_cost = 10
        fees = 5
        transaction_date = $Today
        reason = "Demonstrate recording an opening fact and its original reason."
        target_allocation = 20
        risk_level = "medium"
    } | Out-Null
    Invoke-JarvisJson -Method POST -Path "/investment/transactions" -Body @{
        asset_id = $Asset.id
        transaction_type = "dividend"
        transaction_date = $Today
        cash_amount = 30
        fees = 1
        reason = "Demonstrate a dividend record."
    } | Out-Null
    Invoke-JarvisJson -Method POST -Path "/investment/theses" -Body @{
        asset_id = $Asset.id
        title = "Jarvis Demo Investment Thesis"
        original_reason = "Demonstrate record and review features; not investment advice."
        key_assumptions = @("Fictional operating facts remain stable")
        watch_events = @("Next fictional operating update")
        invalidation_conditions = @("Fictional cash flow deteriorates materially")
        risk_level = "medium"
        cloud_allowed = $false
    } | Out-Null
    Invoke-JarvisJson `
        -Method POST `
        -Path "/investment/assets/$($Asset.id)/news/$($News.id)" `
        -Body @{ relationship_note = "Demo link between intelligence and asset." } | Out-Null
    Invoke-JarvisJson -Method POST -Path "/investment/reviews/generate" -Body @{
        asset_id = $Asset.id
        review_type = "manual"
    } | Out-Null

    Write-Output "Jarvis demo data is ready."
    Write-Output "Dashboard: http://127.0.0.1:3000"
    Write-Output "Remove later with: scripts\demo-data.ps1 -Remove"
}
catch {
    Write-Output "Demo creation stopped. Partial record IDs were saved for safe cleanup."
    Write-Output "Run: scripts\demo-data.ps1 -Remove"
    throw
}
