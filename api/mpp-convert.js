const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFile } = require('child_process')
const { promisify } = require('util')
const { XMLParser } = require('fast-xml-parser')
const XLSX = require('xlsx')

const execFileAsync = promisify(execFile)
const MAX_BYTES = 4 * 1024 * 1024
const PATCHED_MPP_BINARY = path.join(__dirname, '..', 'vendor', 'mppjs', 'linux-x64', 'mpxj-convert')

function asArray(value) {
  if (value == null) return []
  return Array.isArray(value) ? value : [value]
}

function text(value) {
  if (value == null) return ''
  if (typeof value === 'object' && '#text' in value) return String(value['#text'] ?? '')
  return String(value)
}

function isoDate(value) {
  const raw = text(value).trim()
  if (!raw) return ''
  const m = raw.match(/^\d{4}-\d{2}-\d{2}/)
  return m ? m[0] : raw
}

function durationDays(value) {
  const raw = text(value).trim()
  if (!raw) return ''
  const day = raw.match(/P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?)/i)
  if (!day) return raw
  const d = Number(day[1] || 0)
  const h = Number(day[2] || 0)
  const m = Number(day[3] || 0)
  return Math.round((d + h / 8 + m / 480) * 100) / 100
}

function slackDays(value) {
  const raw = text(value).trim()
  if (!raw) return ''
  const sign = raw.startsWith('-') ? -1 : 1
  const clean = raw.replace(/^-/, '')
  const h = clean.match(/PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?/i)
  if (!h) return raw
  return Math.round(sign * ((Number(h[1] || 0) / 8) + (Number(h[2] || 0) / 480)) * 100) / 100
}

function predecessorString(task, uidToId) {
  return asArray(task.PredecessorLink).map((link) => {
    const uid = text(link.PredecessorUID).trim()
    const pred = uidToId.get(uid) || uid
    const typeMap = { '0': 'FF', '1': 'FS', '2': 'SF', '3': 'SS' }
    const rel = typeMap[text(link.Type).trim()] || 'FS'
    const lagMinutes = Number(text(link.LinkLag).trim() || 0) / 10
    const lagDays = lagMinutes / 480
    if (!lagDays) return `${pred}${rel}`
    const sign = lagDays >= 0 ? '+' : ''
    return `${pred}${rel}${sign}${Math.round(lagDays * 100) / 100}d`
  }).filter(Boolean).join(',')
}

function constraintLabel(value) {
  const map = {
    '0': 'As Soon As Possible', '1': 'As Late As Possible', '2': 'Must Start On',
    '3': 'Must Finish On', '4': 'Start No Earlier Than', '5': 'Start No Later Than',
    '6': 'Finish No Earlier Than', '7': 'Finish No Later Than',
  }
  const key = text(value).trim()
  return map[key] || key
}

function writeSheet(wb, name, headers, rows, headerRow = 3) {
  const aoa = []
  while (aoa.length < headerRow - 1) aoa.push([])
  aoa.push(headers)
  rows.forEach((row) => aoa.push(headers.map((h) => row[h] ?? '')))
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(aoa), name)
}

async function readBody(req) {
  const chunks = []
  let size = 0
  for await (const chunk of req) {
    size += chunk.length
    if (size > MAX_BYTES) throw new Error('MPP file exceeds the 4 MB public beta limit.')
    chunks.push(chunk)
  }
  return Buffer.concat(chunks)
}

async function convertWithPatchedMpxj(input, output) {
  if (process.platform !== 'linux' || process.arch !== 'x64') {
    throw new Error(`Native MPP conversion requires Linux x64; received ${process.platform}-${process.arch}.`)
  }
  if (!fs.existsSync(PATCHED_MPP_BINARY)) {
    throw new Error('Patched MPP converter is missing from the deployment bundle.')
  }
  try {
    fs.chmodSync(PATCHED_MPP_BINARY, 0o755)
  } catch (_) {
    // The executable bit is normally preserved by Git/Vercel; chmod is best-effort.
  }
  try {
    await execFileAsync(PATCHED_MPP_BINARY, [input, output], {
      timeout: 50_000,
      maxBuffer: 1024 * 1024,
    })
  } catch (err) {
    const detail = String(err && (err.stderr || err.message) ? (err.stderr || err.message) : err).trim()
    throw new Error(`Patched MPP conversion failed${detail ? `: ${detail}` : '.'}`)
  }
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: { message: 'Method not allowed' } })
  try {
    const filename = String(req.headers['x-file-name'] || 'project.mpp')
    if (!filename.toLowerCase().endsWith('.mpp')) return res.status(415).json({ error: { message: 'Upload a Microsoft Project .mpp file.' } })
    const bytes = await readBody(req)
    if (!bytes.length) return res.status(400).json({ error: { message: 'The MPP file is empty.' } })

    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'controlcheck-mpp-'))
    const input = path.join(tmp, 'input.mpp')
    const output = path.join(tmp, 'output.xml')
    fs.writeFileSync(input, bytes)

    await convertWithPatchedMpxj(input, output)
    const xml = fs.readFileSync(output, 'utf8')
    const parsed = new XMLParser({ ignoreAttributes: false, parseTagValue: false, trimValues: true }).parse(xml)
    const project = parsed.Project || parsed.project
    if (!project) throw new Error('Converted MPP did not contain a valid Microsoft Project XML root.')

    const tasks = asArray(project.Tasks?.Task)
    const uidToId = new Map(tasks.map((t) => [text(t.UID).trim(), text(t.ID || t.UID).trim()]))
    const assignments = asArray(project.Assignments?.Assignment)
    const resources = asArray(project.Resources?.Resource)
    const resourceByUid = new Map(resources.map((r) => [text(r.UID).trim(), text(r.Name).trim()]))
    const resourcesByTask = new Map()
    assignments.forEach((a) => {
      const taskUid = text(a.TaskUID).trim()
      const resourceName = resourceByUid.get(text(a.ResourceUID).trim())
      if (!resourceName) return
      const values = resourcesByTask.get(taskUid) || []
      values.push(resourceName)
      resourcesByTask.set(taskUid, values)
    })

    const flatTasks = tasks.filter((t) => text(t.ID || t.UID).trim() && text(t.Name).trim()).map((t) => {
      const baseline = asArray(t.Baseline)[0] || {}
      const uid = text(t.UID).trim()
      const id = text(t.ID || t.UID).trim()
      const percent = Number(text(t.PercentComplete).trim() || 0)
      const start = isoDate(t.Start)
      const finish = isoDate(t.Finish)
      const baselineStart = isoDate(baseline.Start) || start
      const baselineFinish = isoDate(baseline.Finish) || finish
      const duration = durationDays(t.Duration)
      const totalSlack = slackDays(t.TotalSlack)
      const predecessors = predecessorString(t, uidToId)
      const resourceNames = (resourcesByTask.get(uid) || []).join(', ')
      return {
        'Unique ID': id,
        'Name': text(t.Name).trim(),
        'WBS': text(t.WBS || t.OutlineNumber).trim(),
        'Baseline Start': baselineStart,
        'Baseline Finish': baselineFinish,
        'Start': start,
        'Finish': finish,
        'Duration': duration,
        '% Complete': percent,
        'Total Slack': totalSlack,
        'Predecessors': predecessors,
        'Resource Names': resourceNames,
        'Constraint Type': constraintLabel(t.ConstraintType),
        'Critical': ['1', 'true', 'TRUE'].includes(text(t.Critical).trim()) ? 'true' : 'false',
        'Milestone': ['1', 'true', 'TRUE'].includes(text(t.Milestone).trim()) ? 'true' : 'false',
      }
    })

    if (!flatTasks.length) throw new Error('No usable tasks were found in the MPP file.')

    const projectCode = String(req.headers['x-project-code'] || 'MPP-PROJECT').trim()
    const projectName = String(req.headers['x-project-name'] || text(project.Title || project.Name) || filename.replace(/\.mpp$/i, '')).trim()
    const dataDate = isoDate(project.StatusDate || project.CurrentDate || new Date().toISOString()) || new Date().toISOString().slice(0, 10)

    const wb = XLSX.utils.book_new()
    const taskHeaders = ['Unique ID','Name','WBS','Baseline Start','Baseline Finish','Start','Finish','Duration','% Complete','Total Slack','Predecessors','Resource Names','Constraint Type','Critical','Milestone']
    XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(flatTasks, { header: taskHeaders }), 'Tasks')

    const info = [['field','value'],['project_id',projectCode],['project_name',projectName],['data_date',dataDate],['dataset_version','0.1']]
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(info), 'Project_Info')

    const wbsMap = new Map()
    flatTasks.forEach((t) => {
      const wbs = String(t['WBS'] || '').trim()
      if (!wbs) return
      if (!wbsMap.has(wbs)) wbsMap.set(wbs, { wbs_code: wbs, wbs_name: wbs, parent_wbs: '', discipline: '', level: Math.max(1, wbs.split('.').length) })
    })
    writeSheet(wb, 'WBS', ['wbs_code','wbs_name','parent_wbs','discipline','level'], Array.from(wbsMap.values()))
    writeSheet(wb, 'Budget', ['budget_id','wbs_code','cost_code','description','budget_amount','status','effective_date'], [])
    writeSheet(wb, 'Actual_Cost', ['transaction_id','transaction_date','wbs_code','cost_code','vendor_id','vendor_name','po_number','description','actual_amount','status'], [])
    writeSheet(wb, 'Commitments', ['commitment_id','wbs_code','po_number','vendor_id','vendor_name','committed_amount','invoiced_amount','status','commitment_date'], [])

    const scheduleRows = flatTasks.map((t) => ({
      activity_id: t['Unique ID'],
      wbs_code: t['WBS'],
      activity_name: t['Name'],
      discipline: '',
      baseline_start: t['Baseline Start'],
      baseline_finish: t['Baseline Finish'],
      actual_start: Number(t['% Complete']) > 0 ? t['Start'] : '',
      actual_finish: Number(t['% Complete']) >= 100 ? t['Finish'] : '',
      planned_progress: Number(t['% Complete']) / 100,
      actual_progress: Number(t['% Complete']) / 100,
      total_float_days: Number.isFinite(Number(t['Total Slack'])) ? Math.round(Number(t['Total Slack'])) : 0,
      critical: String(t['Critical']).toLowerCase() === 'true',
      status: Number(t['% Complete']) >= 100 ? 'completed' : Number(t['% Complete']) > 0 ? 'in_progress' : 'not_started',
    }))
    writeSheet(wb, 'Schedule', ['activity_id','wbs_code','activity_name','discipline','baseline_start','baseline_finish','actual_start','actual_finish','planned_progress','actual_progress','total_float_days','critical','status'], scheduleRows)
    writeSheet(wb, 'Progress', ['progress_id','period','wbs_code','planned_progress','actual_progress','variance','status'], [])

    const out = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' })
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    res.setHeader('Content-Disposition', `attachment; filename="${filename.replace(/\.mpp$/i, '')}_ControlCheck.xlsx"`)
    res.setHeader('X-ControlCheck-Task-Count', String(flatTasks.length))
    res.setHeader('X-ControlCheck-MPP-Converter', 'patched-mpxj-headless')
    return res.status(200).send(out)
  } catch (err) {
    console.error('MPP conversion failed', err)
    return res.status(422).json({ error: { message: err && err.message ? err.message : 'MPP conversion failed.' } })
  }
}
