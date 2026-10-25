import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Heatmap.js" as Heatmap

Panel {
  id: root
  moduleName: "bjcatar.garden"
  ipcTarget: "bjcatar.garden"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  // Color.* is undefined when the theme singleton is shadowed or not loaded.
  readonly property color contentForeground: {
    var value = (bar && bar.foreground !== undefined) ? bar.foreground : Color.foreground
    return (value === undefined || value === null) ? "#cacccc" : value
  }
  readonly property color dim: Qt.darker(contentForeground, 1.55)
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color accent: {
    var value = Color.accent
    return (value === undefined || value === null) ? contentForeground : value
  }

  property var snapshot: ({})
  property bool settingsOpen: false
  property bool sheetReady: false
  property bool mutePicker: false
  property string settingsAction: ""
  property string rootToken: ""
  property string settingsStdout: ""
  property var sheet: ({
    version: "",
    roots: [],
    offers: [],
    mutes: [],
    openRepos: [],
    subject: ({ pattern: "", isDefault: true }),
    hardSkipNote: ""
  })
  property int dataRev: 0
  property var last7: []
  property var weeks: []
  property var monthLabels: []
  property string selectedDate: ""
  property string scanHint: ""
  property bool firstScanDone: false
  property double lastScanAt: 0

  property bool pinToday: false
  property string panelView: "year"
  property bool weekCopied: false
  property string selectedProject: ""
  property bool yearPlaced: false

  onPanelViewChanged: {
    weekCopied = false
    if (panelView !== "year" || yearPlaced) return
    yearPlaced = true
    if (yearFlick) {
      yearFlick.pendingToday = true
      Qt.callLater(function() {
        if (yearFlick) yearFlick.scrollToToday()
      })
    }
  }

  readonly property var activityReport: {
    var _ = dataRev
    var report = snapshot && snapshot.activity
    return report && typeof report === "object" ? report : null
  }
  readonly property var weekReport: activityReport && activityReport.week ? activityReport.week : null
  readonly property var projectRows: activityReport && activityReport.projects ? activityReport.projects : []

  function stepView(delta) {
    var order = ["year", "week", "projects"]
    var index = order.indexOf(panelView)
    if (index < 0) index = 0
    var next = index + delta
    if (next < 0) next = order.length - 1
    if (next >= order.length) next = 0
    panelView = order[next]
    selectedProject = ""
  }

  function weekCopyHint() {
    var week = root.weekReport
    if (week && typeof week.copyHint === "string" && week.copyHint.length)
      return week.copyHint
    return "Copies a Markdown week note after a scan."
  }

  function gardenNotify(body) {
    Quickshell.execDetached(["omarchy-notification-send", "Garden", body, "-g", "󰹢"])
  }

  function copyWeek() {
    var markdown = root.weekReport ? root.weekReport.markdown : ""
    if (typeof markdown !== "string" || markdown.indexOf("# This week\n") !== 0) {
      weekCopied = false
      root.gardenNotify("This week fills in after a scan.")
      return
    }
    var omarchyPath = Quickshell.env("OMARCHY_PATH") || "/usr/share/omarchy"
    Quickshell.execDetached([omarchyPath + "/bin/omarchy-clipboard-paste-text", "--copy-only", markdown])
    root.gardenNotify("Week note copied. Paste it into Obsidian.")
    weekCopied = true
    weekCopiedTimer.restart()
  }

  function weekDayColor(day) {
    if (!day || day.future) return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.08)
    var coverage = day.coverage || ""
    if (coverage === "unknown" || coverage === "gap")
      return colorForSlots(0, "unknown")
    if ((day.observedSlots || 0) > 0) return colorForSlots(day.observedSlots, "observed")
    if (coverage === "sampled") return colorForSlots(0, "unknown")
    if ((day.commits || 0) > 0 || coverage === "git-history-only") return colorForSlots(1, "git-history-only")
    if (coverage && coverage !== "observed" && coverage !== "git-history-only" && coverage !== "empty")
      return colorForSlots(0, "unknown")
    return colorForSlots(0, "observed")
  }

  onOpenedChanged: {
    if (opened) {
      weekCopied = false
      yearPlaced = true
      settingsOpen = false
      panelView = "year"
      selectedProject = ""
      pinToday = true
      selectedDate = todayIso
      if (yearFlick) yearFlick.pendingToday = true
      Qt.callLater(function() {
        if (!root.opened) return
        if (yearFlick) yearFlick.scrollToToday()
      })
    } else {
      weekCopied = false
      settingsOpen = false
      if (rootField) rootField.focus = false
    }
  }

  onSettingsOpenChanged: {
    if (settingsOpen) {
      rootToken = ""
      mutePicker = false
      loadSheet()
    } else {
      mutePicker = false
      rootToken = ""
      if (rootField) rootField.focus = false
    }
  }

  readonly property string todayIso: {
    var _ = dataRev
    if (snapshot.today && snapshot.today.date) return snapshot.today.date
    if (snapshot.range && snapshot.range.end) return snapshot.range.end
    var n = new Date()
    return n.getFullYear() + "-" + Heatmap.pad2(n.getMonth() + 1) + "-" + Heatmap.pad2(n.getDate())
  }
  readonly property int todaySlots: {
    var _ = dataRev
    var row = (snapshot.days && snapshot.days[todayIso]) || snapshot.today || {}
    if (row.observedSlots !== undefined) return row.observedSlots || 0
    if (row.coverage === "git-history-only") return 0
    return row.slots || 0
  }
  readonly property string todayHeadline: {
    var _ = dataRev
    var today = snapshot.today
    return (today && today.headline) ? today.headline : ""
  }
  readonly property int totalSlots: snapshot.totalSlots || 0
  readonly property int activeDays: snapshot.activeDays || 0
  readonly property var selectedDay: (snapshot.days && selectedDate) ? snapshot.days[selectedDate] : null

  readonly property int cell: 11
  readonly property int gap: 3
  readonly property int labelW: 26
  readonly property int monthH: 14

  function colorForSlots(slots, coverage) {
    if (coverage === "unknown")
      return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.16)
    var level = Heatmap.dayLevel(slots)
    if (level <= 0)
      return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.22)
    var mix = coverage === "git-history-only" ? [0, 0.18, 0.28, 0.4, 0.55][level] : [0, 0.28, 0.48, 0.72, 1][level]
    return Qt.rgba(accent.r, accent.g, accent.b, mix)
  }

  function applySnapshot(parsed) {
    var previousNote = root.weekReport ? (root.weekReport.markdown || "") : ""
    snapshot = parsed && typeof parsed === "object" ? parsed : {}
    var range = snapshot.range || {}
    var days = snapshot.days || {}
    var end = range.end || todayIso
    var start = range.start || end
    weeks = Heatmap.buildWeeks(start, end, days)
    monthLabels = Heatmap.monthLabels(weeks)
    last7 = Heatmap.lastNDays(end, 7, days)
    if (pinToday || !selectedDate) {
      selectedDate = end
      pinToday = false
    }
    dataRev++
    var nextNote = root.weekReport ? (root.weekReport.markdown || "") : ""
    if (nextNote !== previousNote) weekCopied = false
  }

  function scanBin() {
    var url = Qt.resolvedUrl("bin/garden-scan").toString()
    return decodeURIComponent(url.replace(/^file:\/\//, ""))
  }

  function refresh() {
    if (scanProc.running) return
    root.lastScanAt = Date.now()
    scanProc.running = true
  }

  function scanIfStale() {
    if (scanProc.running) return
    if (root.lastScanAt > 0 && (Date.now() - root.lastScanAt) < 30000) {
      if (dataFile) dataFile.reload()
      return
    }
    root.refresh()
  }

  function maybeFirstScan(empty) {
    if (root.firstScanDone) return
    root.firstScanDone = true
    if (empty) root.refresh()
  }

  function runSettings(action, args) {
    if (settingsProc.running) return
    root.settingsAction = action
    if (action === "read") root.sheetReady = false
    var cmd = ["python3", "-u", root.scanBin()]
    for (var i = 0; i < args.length; i++) cmd.push(args[i])
    settingsProc.command = cmd
    settingsProc.running = true
  }

  function loadSheet() {
    var args = ["--settings-sheet"]
    if (root.rootToken === "home") args.push("--offers")
    root.runSettings("read", args)
  }

  function addRoot() {
    var path = rootField ? rootField.text.trim() : ""
    if (!path) return
    root.runSettings("add", ["--add-root", path])
  }

  function addStored(stored) {
    if (!stored) return
    root.runSettings("add", ["--add-root", stored])
  }

  function removeRoot(stored) {
    root.runSettings("remove", ["--remove-root", stored])
  }

  function muteLabel(label) {
    root.runSettings("mute", ["--mute", label])
  }

  function unmuteStored(stored) {
    root.runSettings("unmute", ["--unmute", stored])
  }

  function rootNote(token) {
    if (!token || token === "empty") return ""
    if (token === "home") return "Your home folder is too broad. Pick a folder inside it."
    if (token === "missing") return "That folder does not exist."
    if (token === "not-directory") return "That path is not a folder."
    if (token === "outside-home") return "Pick a folder inside your home."
    return "That folder was rejected (must be inside your home, not your home directory itself)."
  }

  function scanStatusLine() {
    var status = root.snapshot.scanStatus
    if (status) return status
    if (root.snapshot.timerEnabled === true)
      return "No successful scan yet. Timer enabled."
    return "No successful scan yet. Timer off."
  }

  function finishSettingsCommand(code, captured) {
    var text = String(captured !== undefined ? captured : (root.settingsStdout || "")).trim()
    var parsed = null
    try {
      parsed = JSON.parse(text)
    } catch (e) {
      parsed = null
    }
    if (!parsed || typeof parsed !== "object" || parsed.result === undefined) {
      if (code === 2) root.rootToken = "home"
      else if (code === 1) root.rootToken = "reject"
      return
    }
    root.sheet = parsed
    root.sheetReady = true
    if (root.settingsAction === "read") return
    root.rootToken = parsed.token || ""
    if (parsed.result === "home" || parsed.result === "reject") return
    if (root.settingsAction === "add" && parsed.result === "ok") {
      if (rootField) rootField.text = ""
      root.rootToken = ""
      if (root.opened && keyCatcher) keyCatcher.forceActiveFocus()
      root.refresh()
      return
    }
    if (parsed.result === "ok") root.refresh()
  }

  function open() {
    pinToday = true
    setCenterHoverRevealSuppressed(true)
    root.controller.show()
  }

  function close() {
    // Release the input surfaces before doing optional bar/field cleanup.
    root.controller.hide()
    if (rootField) rootField.focus = false
    setCenterHoverRevealSuppressed(false)
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function setCenterHoverRevealSuppressed(value) {
    // Installed plugins receive PluginBarApi, whose scalar state is read-only.
    // Use its public setter; cosmetic failures must never block dismissal.
    try {
      if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
        root.bar.setCenterHoverRevealSuppressed(value)
    } catch (e) {
      console.warn("garden", "Could not update bar hover state:", e)
    }
  }

  function moveDay(delta) {
    if (!weeks.length) return
    var iso = selectedDate || todayIso
    var d = Heatmap.parseIso(iso)
    d.setDate(d.getDate() + delta)
    var next = Heatmap.isoLocal(d)
    if (snapshot.days && snapshot.days[next] !== undefined)
      selectedDate = next
  }

  FileView {
    id: dataFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/garden/heatmap.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try { root.applySnapshot(JSON.parse(String(text() || "{}"))) }
      catch (e) { console.warn("garden", "bad heatmap.json", e) }
      var days = root.snapshot.days
      var empty = !days || Object.keys(days).length === 0
      root.maybeFirstScan(empty)
    }
  }

  Process {
    id: scanProc
    command: ["python3", root.scanBin()]
    onExited: function(code) {
      root.scanHint = code === 0 ? "" : "Scan failed (exit " + code + ")."
      dataFile.reload()
      if (root.settingsOpen) root.loadSheet()
    }
  }

  Process {
    id: settingsProc
    stdout: SplitParser {
      onRead: function(line) {
        root.settingsStdout += line
      }
    }
    onStarted: root.settingsStdout = ""
    onExited: function(code) {
      var status = code
      var captured = String(root.settingsStdout || "")
      Qt.callLater(function() { root.finishSettingsCommand(status, captured) })
    }
  }

  Timer {
    id: weekCopiedTimer
    interval: 1600
    onTriggered: root.weekCopied = false
  }

  Process {
    id: timerProc
    onExited: function(code) {
      if (code !== 0) {
        root.scanHint = "Could not enable background scan (exit " + code + ")."
        return
      }
      root.refresh()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    onFocusPrimedChanged: {
      if (open && focusPrimed) root.scanIfStale()
    }
    contentWidth: panel.fittedContentWidth(Style.space(680))
    contentHeight: panel.fittedContentHeight(body.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      blocked: !!(rootField && rootField.activeFocus)
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.refresh()
      onMoveRequested: function(dx, dy) {
        if (root.settingsOpen) return
        if (root.panelView !== "year") {
          if (dx < 0) root.stepView(-1)
          else if (dx > 0) root.stepView(1)
          return
        }
        if (dx !== 0) root.moveDay(dx)
        if (dy !== 0) root.moveDay(dy * 7)
      }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
        else if ((t === "c" || t === "C") && root.panelView === "week" && !root.settingsOpen) root.copyWeek()
      }

      Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height

        Column {
          id: body
          width: flick.width
          spacing: Style.space(10)
          leftPadding: Style.space(16)
          rightPadding: Style.space(16)
          topPadding: Style.space(14)
          bottomPadding: Style.space(16)

          Row {
            width: parent.width - parent.leftPadding - parent.rightPadding
            spacing: Style.space(12)

            Text {
              width: parent.width - refreshBtn.implicitWidth - parent.spacing
              text: {
                if (scanProc.running) return "Scanning this machine…"
                var today = root.snapshot.today
                var headline = today ? today.headline : ""
                if (headline) return headline
                var h = Heatmap.hoursActive(root.todaySlots)
                if (h <= 0) return "This Omarchy box is waiting for you"
                if (h === 0.5) return "You built a half hour here today"
                if (h === 1) return "You built 1 hour here today"
                return "You built " + h + " hours here today"
              }
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.body
              font.bold: true
              wrapMode: Text.WordWrap
            }

            Text {
              id: refreshBtn
              text: scanProc.running ? "…" : "Refresh"
              color: scanProc.running ? root.dim : root.accent
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              anchors.verticalCenter: parent.verticalCenter
              MouseArea {
                anchors.fill: parent
                enabled: !scanProc.running
                cursorShape: Qt.PointingHandCursor
                onClicked: root.refresh()
              }
            }
          }

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: "A half-hour counts when a file changed here. Commits without a save do not add hours."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Text {
            visible: root.scanHint !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: root.scanHint
            color: root.dim
            wrapMode: Text.WordWrap
            font.pixelSize: Style.font.caption
            font.family: root.contentFontFamily
          }

          Row {
            spacing: Style.space(14)
            Text {
              text: "Year"
              color: root.panelView === "year" ? root.accent : root.dim
              font.bold: root.panelView === "year"
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  root.settingsOpen = false
                  root.panelView = "year"
                  root.selectedProject = ""
                }
              }
            }
            Text {
              text: "This week"
              color: root.panelView === "week" ? root.accent : root.dim
              font.bold: root.panelView === "week"
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  root.settingsOpen = false
                  root.panelView = "week"
                  root.selectedProject = ""
                }
              }
            }
            Text {
              text: "Projects"
              color: root.panelView === "projects" ? root.accent : root.dim
              font.bold: root.panelView === "projects"
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  root.settingsOpen = false
                  root.panelView = "projects"
                  root.selectedProject = ""
                }
              }
            }
            Text {
              text: "Settings"
              color: root.settingsOpen ? root.accent : root.dim
              font.bold: root.settingsOpen
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.settingsOpen = !root.settingsOpen
              }
            }
          }

          Text {
            visible: root.panelView !== "year" && !root.settingsOpen && text !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: root.weekReport ? (root.weekReport.overlap || "") : ""
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
            id: weekBlock
            visible: root.panelView === "week" && !root.settingsOpen
            height: visible ? implicitHeight : 0
            width: parent.width - parent.leftPadding - parent.rightPadding
            spacing: Style.space(8)

            Text {
              width: parent.width
              text: {
                var _ = root.dataRev
                return root.weekReport ? (root.weekReport.headline || "") : "This week fills in after a scan."
              }
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              wrapMode: Text.WordWrap
            }

            Rectangle {
              id: weekCopyBox
              width: parent.width
              radius: 4
              color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.08)
              implicitHeight: copyRow.y + copyRow.implicitHeight + Style.space(8)
              height: implicitHeight

              Row {
                id: copyRow
                x: Style.space(10)
                y: Style.space(8)
                width: parent.width - x - Style.space(10)
                spacing: Style.space(12)

                Text {
                  id: weekCopyHint
                  width: parent.width - weekCopy.implicitWidth - parent.spacing
                  text: {
                    var _ = root.dataRev
                    return root.weekCopyHint()
                  }
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.WordWrap
                }

                Text {
                  id: weekCopy
                  text: root.weekCopied ? "Copied" : "Copy Markdown"
                  color: root.accent
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.copyWeek()
              }
            }

            Row {
              spacing: 6
              visible: !!root.weekReport
              Repeater {
                model: root.weekReport ? root.weekReport.days : []
                Column {
                  required property var modelData
                  spacing: 3
                  Rectangle {
                    width: 28
                    height: 18
                    radius: 2
                    color: root.weekDayColor(modelData)
                    MouseArea {
                      anchors.fill: parent
                      enabled: !modelData.future
                      cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                      onClicked: {
                        root.selectedDate = modelData.date
                        root.panelView = "year"
                      }
                    }
                  }
                  Text {
                    width: 28
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData.weekday
                    color: root.dim
                    font.family: root.contentFontFamily
                    font.pixelSize: 9
                  }
                  Text {
                    width: 28
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData.caption || ""
                    color: root.dim
                    font.family: root.contentFontFamily
                    font.pixelSize: 9
                  }
                }
              }
            }

            Repeater {
              model: root.weekReport ? root.weekReport.spans : []
              Text {
                required property var modelData
                width: weekBlock.width
                text: modelData.line || ""
                color: root.dim
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
              }
            }

            Text {
              visible: !!(root.weekReport && root.weekReport.recentCommits && root.weekReport.recentCommits.length)
              text: "Recent commits"
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Repeater {
              model: (root.weekReport && root.weekReport.recentCommits) ? root.weekReport.recentCommits : []
              Text {
                required property var modelData
                width: weekBlock.width
                text: modelData.line || ""
                color: root.dim
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
            }
          }

          Column {
            id: projectBlock
            visible: root.panelView === "projects" && !root.settingsOpen
            height: visible ? implicitHeight : 0
            width: parent.width - parent.leftPadding - parent.rightPadding
            spacing: Style.space(8)

            Text {
              visible: !root.activityReport
              width: parent.width
              text: "Projects fill in after a scan."
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.WordWrap
            }

            Text {
              visible: !!root.activityReport && root.projectRows.length === 0
              width: parent.width
              text: "No projects yet."
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            Repeater {
              model: root.projectRows
              Column {
                id: projectRow
                required property var modelData
                width: projectBlock.width
                spacing: 2
                Text {
                  width: parent.width
                  text: projectRow.modelData.name
                  color: root.selectedProject === projectRow.modelData.name ? root.accent : root.contentForeground
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  elide: Text.ElideMiddle
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selectedProject = root.selectedProject === projectRow.modelData.name ? "" : projectRow.modelData.name
                  }
                }
                Text {
                  width: parent.width
                  text: projectRow.modelData.touched || ""
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.WordWrap
                }
                Column {
                  width: parent.width
                  visible: root.selectedProject === projectRow.modelData.name
                  height: visible ? implicitHeight : 0
                  spacing: 2
                  Repeater {
                    model: projectRow.modelData.windows || []
                    Text {
                      required property var modelData
                      width: projectBlock.width
                      text: modelData.line || ""
                      color: root.dim
                      font.family: root.contentFontFamily
                      font.pixelSize: Style.font.caption
                      wrapMode: Text.WordWrap
                    }
                  }
                  Repeater {
                    model: projectRow.modelData.recentCommits || []
                    Text {
                      required property var modelData
                      width: projectBlock.width
                      text: modelData.line || ""
                      color: root.dim
                      font.family: root.contentFontFamily
                      font.pixelSize: Style.font.caption
                      elide: Text.ElideRight
                    }
                  }
                }
              }
            }
          }

          Text {
            visible: root.panelView === "year" && !root.settingsOpen && !!(root.snapshot.review && root.snapshot.review.sentence)
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: (root.snapshot.review && root.snapshot.review.sentence) ? root.snapshot.review.sentence : ""
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
            visible: root.panelView === "year" && !root.settingsOpen
            height: visible ? implicitHeight : 0
            spacing: Style.space(4)
            width: parent.width - parent.leftPadding - parent.rightPadding

            Row {
              spacing: 0
              width: parent.width

              Item {
                width: root.labelW
                height: root.monthH + 7 * (root.cell + root.gap)
                Column {
                  y: root.monthH
                  width: root.labelW
                  spacing: root.gap
                  Repeater {
                    model: Heatmap.WEEKDAY_LABELS
                    Text {
                      required property var modelData
                      width: root.labelW - 4
                      height: root.cell
                      text: modelData
                      color: root.dim
                      font.family: root.contentFontFamily
                      font.pixelSize: 9
                      horizontalAlignment: Text.AlignRight
                      verticalAlignment: Text.AlignVCenter
                    }
                  }
                }
              }

              Flickable {
                id: yearFlick
                width: parent.width - root.labelW
                height: root.monthH + 7 * (root.cell + root.gap)
                clip: true
                contentWidth: Math.max(width, root.weeks.length * (root.cell + root.gap))
                contentHeight: height
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                property bool pendingToday: true
                function scrollToToday() {
                  contentX = Math.max(0, contentWidth - width)
                  pendingToday = false
                }
                onContentWidthChanged: if (pendingToday) Qt.callLater(scrollToToday)

                Column {
                  spacing: 0
                  Item {
                    width: root.weeks.length * (root.cell + root.gap)
                    height: root.monthH
                    Repeater {
                      model: root.monthLabels
                      Text {
                        required property var modelData
                        x: modelData.index * (root.cell + root.gap)
                        text: modelData.label
                        color: root.dim
                        font.family: root.contentFontFamily
                        font.pixelSize: 10
                      }
                    }
                  }
                  Row {
                    spacing: root.gap
                    Repeater {
                      model: root.weeks
                      Column {
                        id: weekCol
                        required property var modelData
                        spacing: root.gap
                        Repeater {
                          model: weekCol.modelData
                          Rectangle {
                            required property var modelData
                            width: root.cell
                            height: root.cell
                            radius: 2
                            color: {
                              if (!modelData.inRange) return "transparent"
                              if (modelData.paint === "pale" || modelData.coverage === "git-history-only")
                                return root.colorForSlots(modelData.slots || 0, "git-history-only")
                              if (modelData.paint === "dim" || modelData.coverage === "unknown")
                                return root.colorForSlots(0, "unknown")
                              return root.colorForSlots(modelData.observedSlots || 0, "observed")
                            }
                            border.width: modelData.date === root.todayIso ? 2 : (root.selectedDate === modelData.date ? 1 : 0)
                            border.color: root.accent
                            opacity: modelData.inRange ? 1 : 0
                            MouseArea {
                              anchors.fill: parent
                              enabled: modelData.inRange
                              hoverEnabled: true
                              cursorShape: Qt.PointingHandCursor
                              onClicked: root.selectedDate = modelData.date
                              PanelToolTip {
                                visible: parent.containsMouse && modelData.inRange
                                text: {
                                  if (modelData.label) return modelData.label
                                  var cov = modelData.coverage || ""
                                  if (cov === "unknown")
                                    return "not monitored yet · " + Heatmap.prettyDate(modelData.date)
                                  if (cov === "git-history-only") {
                                    var c = modelData.commits || 0
                                    return (c ? (c + " commit" + (c === 1 ? "" : "s") + " · ") : "") + "git history only · " + Heatmap.prettyDate(modelData.date)
                                  }
                                  var n = (modelData.observedSlots !== undefined) ? modelData.observedSlots : (modelData.slots || 0)
                                  return Heatmap.hoursActive(n) + "h on this PC · " + Heatmap.prettyDate(modelData.date)
                                }
                                fontFamily: root.contentFontFamily
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }

            Row {
              width: parent.width
              spacing: 8
              Text {
                text: yearFlick.contentX > 8 ? "← earlier" : "This year"
                color: root.dim
                font.pixelSize: 10
                font.family: root.contentFontFamily
              }
              Item { width: 8; height: 1 }
              Text { text: "Less"; color: root.dim; font.pixelSize: 10; font.family: root.contentFontFamily }
              Repeater {
                model: 5
                Rectangle {
                  required property int index
                  width: root.cell
                  height: root.cell
                  radius: 2
                  color: root.colorForSlots(index === 0 ? 0 : (index === 1 ? 1 : (index === 2 ? 3 : (index === 3 ? 6 : 10))), "observed")
                }
              }
              Text { text: "More"; color: root.dim; font.pixelSize: 10; font.family: root.contentFontFamily }
              Text {
                text: "now →"
                color: root.dim
                font.pixelSize: 10
                font.family: root.contentFontFamily
              }
            }
          }

          Text {
            visible: root.panelView === "year" && !root.settingsOpen && root.selectedDate !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
            wrapMode: Text.WordWrap
            text: {
              if (!root.selectedDate) return ""
              var d = root.selectedDay || {}
              if (d.label) {
                var extra = []
                if (d.commits) extra.push(d.commits + " commits")
                if (d.files) extra.push(d.files + " files touched")
                if (d.repos && d.repos.length) extra.push(d.repos.join(" · "))
                return extra.length ? d.label + " · " + extra.join(" · ") : d.label
              }
              var bits = [Heatmap.prettyDate(root.selectedDate)]
              bits.push(Heatmap.hoursActive(d.observedSlots !== undefined ? d.observedSlots : (d.coverage === "git-history-only" ? 0 : (d.slots || 0))) + "h observed")
              if (d.commits) bits.push(d.commits + " commits")
              if (d.files) bits.push(d.files + " files touched")
              if (d.coverage === "git-history-only") bits.push("git history only — may not have happened on this PC")
              if (d.coverage === "unknown") bits.push("not monitored yet")
              if (d.repos && d.repos.length) bits.push(d.repos.join(" · "))
              return bits.join(" · ")
            }
          }

          Text {
            visible: root.panelView === "year" && !root.settingsOpen && root.selectedDate !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: "This day, half-hour by half-hour"
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: 10
          }

          Row {
            visible: root.panelView === "year" && !root.settingsOpen && root.selectedDate !== ""
            height: visible ? implicitHeight : 0
            spacing: 1
            width: parent.width - parent.leftPadding - parent.rightPadding
            Repeater {
              model: 48
              Rectangle {
                required property int index
                width: Math.max(2, Math.floor((body.width - body.leftPadding - body.rightPadding - 47) / 48))
                height: 8
                radius: 1
                color: {
                  var _ = root.dataRev
                  var d = root.selectedDay || {}
                  var idxs = d.slotIndexes || []
                  var lit = false
                  for (var i = 0; i < idxs.length; i++) if (idxs[i] === index) lit = true
                  return lit ? root.accent : Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.16)
                }
              }
            }
          }

          Text {
            visible: root.panelView === "year" && !root.settingsOpen && !!(root.selectedDate !== "" && root.selectedDay && root.selectedDay.bySlot)
            width: parent.width - parent.leftPadding - parent.rightPadding
            wrapMode: Text.WordWrap
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: 10
            text: {
              var d = root.selectedDay || {}
              var by = d.bySlot || {}
              var idxs = d.slotIndexes || []
              var lines = []
              for (var i = 0; i < idxs.length; i++) {
                var s = idxs[i]
                var info = by[String(s)] || {}
                var hh = Math.floor(s / 2)
                var mm = (s % 2) ? "30" : "00"
                var label = (hh < 10 ? "0" : "") + hh + ":" + mm
                var bits = [label]
                if (info.git) bits.push(info.git + " commit" + (info.git === 1 ? "" : "s"))
                if (info.file) bits.push(info.file + " file" + (info.file === 1 ? "" : "s"))
                var repos = info.repos || []
                if (repos.length) bits.push(repos.join(", "))
                lines.push(bits.join(" · "))
              }
              return lines.join("\n")
            }
          }

          Column {
            id: settingsBlock
            visible: root.settingsOpen
            height: visible ? implicitHeight : 0
            width: parent.width - parent.leftPadding - parent.rightPadding
            spacing: Style.space(8)

            Text {
              visible: (root.sheet.version || "") !== ""
              text: "Garden " + root.sheet.version
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }

            Text {
              width: parent.width
              text: {
                var _ = root.dataRev
                return root.scanStatusLine()
              }
              wrapMode: Text.WordWrap
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }

            Text {
              visible: root.snapshot.timerEnabled !== true
              text: "Enable background scan"
              color: root.accent
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  timerProc.command = ["python3", root.scanBin(), "--install-timer"]
                  timerProc.running = true
                }
              }
            }

            Text {
              text: "Watching"
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Text {
              visible: root.sheetReady && !(root.sheet.roots || []).length
              width: parent.width
              text: "Nothing is watched. Add a folder below."
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            Repeater {
              model: root.sheet.roots || []
              Column {
                required property var modelData
                width: settingsBlock.width
                spacing: 2
                Row {
                  width: parent.width
                  spacing: Style.space(8)
                  Text {
                    text: modelData.display ? modelData.display : modelData.stored
                    color: modelData.ok ? root.dim : root.contentForeground
                    font.family: root.contentFontFamily
                    font.pixelSize: Style.font.caption
                    elide: Text.ElideMiddle
                    width: parent.width - Style.space(48)
                  }
                  Text {
                    text: "×"
                    color: root.contentForeground
                    font.pixelSize: Style.font.body
                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      enabled: !settingsProc.running
                      onClicked: root.removeRoot(modelData.stored)
                    }
                  }
                }
                Text {
                  visible: root.rootNote(modelData.token || "") !== ""
                  width: parent.width
                  text: root.rootNote(modelData.token || "")
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.WordWrap
                }
              }
            }

            Row {
              spacing: Style.space(8)
              width: parent.width
              TextField {
                id: rootField
                width: parent.width - Style.space(72)
                anchors.verticalCenter: parent.verticalCenter
                placeholderText: "Folder to watch"
                foreground: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                horizontalPadding: Style.spacing.controlGap
                verticalPadding: Style.spacing.controlPaddingY
                activeFocusOnTab: false
                onAccepted: root.addRoot()
                Keys.onEscapePressed: root.close()
              }
              Text {
                text: "Add"
                color: root.accent
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  enabled: !settingsProc.running
                  onClicked: root.addRoot()
                }
              }
            }

            Text {
              visible: root.rootNote(root.rootToken) !== ""
              width: parent.width
              text: root.rootNote(root.rootToken)
              color: root.dim
              wrapMode: Text.WordWrap
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }

            Column {
              visible: (root.sheet.offers || []).length > 0
              width: parent.width
              spacing: Style.space(4)
              height: visible ? implicitHeight : 0
              Text {
                text: "Folders in your home"
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
              }
              Repeater {
                model: root.sheet.offers || []
                Text {
                  required property var modelData
                  width: settingsBlock.width
                  text: modelData.display ? modelData.display : modelData.stored
                  color: root.accent
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideMiddle
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: !settingsProc.running
                    onClicked: root.addStored(modelData.stored)
                  }
                }
              }
            }

            Text {
              visible: (root.sheet.hardSkipNote || "") !== ""
              width: parent.width
              text: root.sheet.hardSkipNote || ""
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            Text {
              visible: !!(root.sheet.subject && root.sheet.subject.pattern)
              width: parent.width
              text: "Ignored commit subjects: " + (root.sheet.subject ? root.sheet.subject.pattern : "")
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              wrapMode: Text.WordWrap
            }

            Repeater {
              model: root.sheet.mutes || []
              Row {
                required property var modelData
                width: settingsBlock.width
                spacing: Style.space(8)
                Text {
                  width: parent.width - Style.space(72)
                  text: {
                    var hits = modelData.hits || []
                    var line = modelData.stored || ""
                    if (hits.length) line += " · " + hits.join(", ")
                    return line
                  }
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.WordWrap
                }
                Text {
                  text: "Unmute"
                  color: root.accent
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: !settingsProc.running
                    onClicked: root.unmuteStored(modelData.stored)
                  }
                }
              }
            }

            Text {
              visible: root.mutePicker || (root.sheet.openRepos || []).length > 0
              text: "Mute a project"
              color: root.mutePicker ? root.contentForeground : root.accent
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.mutePicker = !root.mutePicker
              }
            }

            Repeater {
              model: root.mutePicker ? (root.sheet.openRepos || []) : []
              Row {
                required property var modelData
                width: settingsBlock.width
                spacing: Style.space(8)
                Text {
                  width: parent.width - Style.space(48)
                  text: modelData
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideMiddle
                }
                Text {
                  text: "Mute"
                  color: root.accent
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: !settingsProc.running
                    onClicked: root.muteLabel(modelData)
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
