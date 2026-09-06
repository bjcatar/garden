// Date math for the Garden heatmap. Qt-free so QML just paints.
var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
var WEEKDAY_LABELS = ["", "Mon", "", "Wed", "", "Fri", ""]

function pad2(n) {
  return (n < 10 ? "0" : "") + n
}

function isoLocal(d) {
  return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
}

function parseIso(iso) {
  var p = String(iso || "").split("-")
  if (p.length < 3) return new Date()
  return new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]))
}

function prettyDate(iso) {
  var d = parseIso(iso)
  var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
  return days[d.getDay()] + ", " + MONTHS[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear()
}

function cellFor(days, iso) {
  if (!days || !days[iso]) return { slots: 0, commits: 0, files: 0, agents: 0, repos: [], coverage: "empty" }
  return days[iso]
}

function dayLevel(slots) {
  var n = slots || 0
  if (n <= 0) return 0
  if (n <= 1) return 1
  if (n <= 3) return 2
  if (n <= 7) return 3
  return 4
}

function hoursActive(slots) {
  return (slots || 0) * 0.5
}

function buildWeeks(startIso, endIso, days) {
  var start = parseIso(startIso)
  var end = parseIso(endIso)
  var cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate())
  cursor.setDate(cursor.getDate() - cursor.getDay())
  var weeks = []
  var guard = 0
  while (guard++ < 53) {
    var week = []
    for (var i = 0; i < 7; i++) {
      var iso = isoLocal(cursor)
      var inRange = cursor >= start && cursor <= end
      var cell = inRange ? cellFor(days, iso) : null
      week.push({
        date: iso,
        inRange: inRange,
        slots: cell ? (cell.slots || 0) : 0,
        commits: cell ? (cell.commits || 0) : 0,
        files: cell ? (cell.files || 0) : 0,
        coverage: cell ? (cell.coverage || "empty") : "empty",
        repos: cell && cell.repos ? cell.repos : []
      })
      cursor.setDate(cursor.getDate() + 1)
    }
    weeks.push(week)
    if (cursor > end) break
  }
  return weeks
}

function monthLabels(weeks) {
  var labels = []
  var last = -1
  for (var i = 0; i < weeks.length; i++) {
    var week = weeks[i]
    var first = null
    for (var d = 0; d < week.length; d++) {
      if (week[d].inRange) { first = week[d]; break }
    }
    if (!first) continue
    var month = parseIso(first.date).getMonth()
    if (month !== last) {
      labels.push({ index: i, month: month, label: MONTHS[month] })
      last = month
    }
  }
  return labels
}

function lastNDays(endIso, n, days) {
  var end = parseIso(endIso)
  var out = []
  for (var i = n - 1; i >= 0; i--) {
    var d = new Date(end.getFullYear(), end.getMonth(), end.getDate() - i)
    var iso = isoLocal(d)
    var cell = cellFor(days, iso)
    out.push({
      date: iso,
      slots: cell.slots || 0,
      coverage: cell.coverage || "empty"
    })
  }
  return out
}
