import QtQuick
import QtQuick.Controls
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
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(contentForeground, 1.55)
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property color accent: Color.accent

  property var snapshot: ({})
  property var gardenSettings: ({ roots: [] })
  property int dataRev: 0
  property var last7: []
  property var weeks: []
  property var monthLabels: []
  property string selectedDate: ""
  property string rootDraft: ""
  property string scanHint: ""
  property bool firstScanDone: false
  property double lastScanAt: 0

  onOpenedChanged: if (opened) {
    if (yearFlick) yearFlick.pendingToday = true
    Qt.callLater(function() { if (yearFlick) yearFlick.scrollToToday() })
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
    if (row.coverage === "git-history-only") return 0
    return row.slots || 0
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
    snapshot = parsed && typeof parsed === "object" ? parsed : {}
    var range = snapshot.range || {}
    var days = snapshot.days || {}
    var end = range.end || todayIso
    var start = range.start || end
    weeks = Heatmap.buildWeeks(start, end, days)
    monthLabels = Heatmap.monthLabels(weeks)
    last7 = Heatmap.lastNDays(end, 7, days)
    if (!selectedDate) selectedDate = todayIso
    dataRev++
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

  function addRoot() {
    var path = rootDraft.trim()
    if (!path) return
    addProc.command = ["python3", scanBin(), "--add-root", path]
    addProc.running = true
  }

  function removeRoot(path) {
    rmProc.command = ["python3", scanBin(), "--remove-root", path]
    rmProc.running = true
  }

  function open() {
    root.scanIfStale()
    if (dataFile) dataFile.reload()
    if (settingsFile) settingsFile.reload()
    root.controller.show()
    Qt.callLater(function() {
      if (root.opened) setCenterHoverRevealSuppressed(true)
    })
  }

  function close() {
    setCenterHoverRevealSuppressed(false)
    root.controller.hide()
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
    if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
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

  FileView {
    id: settingsFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/garden/settings.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try { root.gardenSettings = JSON.parse(String(text() || "{}")) }
      catch (e) { root.gardenSettings = { roots: [] } }
    }
  }

  Process {
    id: scanProc
    command: ["python3", root.scanBin()]
    onExited: function(code) {
      root.scanHint = code === 0 ? "" : "Scan failed (exit " + code + ")."
      dataFile.reload()
      settingsFile.reload()
    }
  }

  Process {
    id: addProc
    onExited: function(code) {
      if (code !== 0) {
        root.scanHint = "That folder was rejected (must be inside your home, not your home directory itself)."
        return
      }
      root.rootDraft = ""
      root.scanHint = ""
      root.refresh()
    }
  }

  Process {
    id: rmProc
    onExited: function() { root.refresh() }
  }

  Process {
    id: timerProc
    onExited: function() { root.refresh() }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(680))
    contentHeight: panel.fittedContentHeight(body.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.refresh()
      onMoveRequested: function(dx, dy) {
        if (dx !== 0) root.moveDay(dx)
        if (dy !== 0) root.moveDay(dy * 7)
      }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
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
              text: scanProc.running
                ? "Scanning this machine…"
                : (root.todaySlots <= 0
                  ? "This Omarchy box is waiting for you"
                  : ("You built " + Heatmap.hoursActive(root.todaySlots) + " hours here today"))
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
            text: "Hours are half-hours you showed up — six commits in one window is still 0.5h, not a busy GitHub day."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Text {
            visible: !!(root.snapshot.review && root.snapshot.review.sentence)
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: (root.snapshot.review && root.snapshot.review.sentence) ? root.snapshot.review.sentence : ""
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
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
                              return root.colorForSlots(modelData.slots, modelData.coverage)
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
                                text: Heatmap.hoursActive(modelData.slots) + "h on this PC · " + Heatmap.prettyDate(modelData.date)
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
              Item { width: parent.width > 1 ? 1 : 1; height: 1 }
              Text {
                text: "now →"
                color: root.dim
                font.pixelSize: 10
                font.family: root.contentFontFamily
              }
            }
          }

          Text {
            visible: root.selectedDate !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
            wrapMode: Text.WordWrap
            text: {
              if (!root.selectedDate) return ""
              var d = root.selectedDay || {}
              var bits = [Heatmap.prettyDate(root.selectedDate)]
              bits.push(Heatmap.hoursActive(d.slots || 0) + "h observed")
              if (d.commits) bits.push(d.commits + " commits")
              if (d.files) bits.push(d.files + " files touched")
              if (d.coverage === "git-history-only") bits.push("git history only — may not have happened on this PC")
              if (d.coverage === "unknown") bits.push("not monitored yet")
              if (d.repos && d.repos.length) bits.push(d.repos.join(" · "))
              return bits.join(" · ")
            }
          }

          Text {
            visible: root.selectedDate !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: "This day, half-hour by half-hour"
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: 10
          }

          Row {
            visible: root.selectedDate !== ""
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
            visible: !!(root.selectedDate !== "" && root.selectedDay && root.selectedDay.bySlot)
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

          Text {
            text: "Watching"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }

          Text {
            visible: !(root.gardenSettings.roots || root.snapshot.roots || []).length
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: "Nothing is watched. Add a folder below."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Repeater {
            model: root.gardenSettings.roots || root.snapshot.roots || []
            Row {
              required property var modelData
              spacing: Style.space(8)
              width: body.width - body.leftPadding - body.rightPadding
              Text {
                text: modelData
                color: root.dim
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
                  onClicked: root.removeRoot(modelData)
                }
              }
            }
          }

          Row {
            spacing: Style.space(8)
            width: body.width - body.leftPadding - body.rightPadding
            TextInput {
              id: rootField
              width: parent.width - Style.space(72)
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
              text: root.rootDraft
              onTextChanged: root.rootDraft = text
              Keys.onReturnPressed: root.addRoot()
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
                onClicked: root.addRoot()
              }
            }
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

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: snapshot.timerEnabled ? "Background scan is on (every 15 min)." : "Background scan is off."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
          }

          Text {
            visible: snapshot.timerEnabled !== true
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
        }
      }
    }
  }
}
