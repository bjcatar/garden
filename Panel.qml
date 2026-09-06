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

  readonly property string todayIso: {
    var n = new Date()
    return n.getFullYear() + "-" + Heatmap.pad2(n.getMonth() + 1) + "-" + Heatmap.pad2(n.getDate())
  }
  readonly property int todaySlots: {
    var _ = dataRev
    var row = (snapshot.days && snapshot.days[todayIso]) || snapshot.today || {}
    return row.slots || 0
  }
  readonly property int totalSlots: snapshot.totalSlots || 0
  readonly property int activeDays: snapshot.activeDays || 0
  readonly property var selectedDay: (snapshot.days && selectedDate) ? snapshot.days[selectedDate] : null

  readonly property int cell: 9
  readonly property int gap: 2
  readonly property int labelW: 26
  readonly property int monthH: 14

  function colorForSlots(slots, coverage) {
    if (coverage === "unknown")
      return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.05)
    var level = Heatmap.dayLevel(slots)
    if (level <= 0)
      return Qt.rgba(contentForeground.r, contentForeground.g, contentForeground.b, 0.12)
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
    dataRev++
  }

  function scanBin() {
    var url = Qt.resolvedUrl("bin/garden-scan").toString()
    return url.replace(/^file:\/\//, "")
  }

  function refresh() {
    if (!scanProc.running) scanProc.running = true
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
    else
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
    onExited: function() {
      root.scanHint = ""
      dataFile.reload()
      settingsFile.reload()
    }
  }

  Process {
    id: addProc
    onExited: function(code) {
      root.rootDraft = ""
      root.scanHint = code === 0 ? "" : "That folder was rejected (must be inside your home, not $HOME itself)."
      root.refresh()
    }
  }

  Process {
    id: rmProc
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

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: root.totalSlots <= 0
              ? "Nothing observed on this PC yet"
              : (Heatmap.hoursActive(root.totalSlots) + " active hours on this PC · last year")
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.body
            font.bold: true
            wrapMode: Text.WordWrap
          }

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: root.activeDays + " active days · squares are half-hours you or an agent touched a watched folder — not GitHub"
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
            spacing: Style.space(4)

            Item {
              width: Math.min(parent.parent.width - 32, root.labelW + root.weeks.length * (root.cell + root.gap))
              height: root.monthH
              Repeater {
                model: root.monthLabels
                Text {
                  required property var modelData
                  x: root.labelW + modelData.index * (root.cell + root.gap)
                  text: modelData.label
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: 10
                }
              }
            }

            Row {
              Column {
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

              Flickable {
                width: Math.min(Style.space(560), root.weeks.length * (root.cell + root.gap))
                height: 7 * (root.cell + root.gap)
                clip: true
                contentWidth: root.weeks.length * (root.cell + root.gap)
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds

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
                          color: modelData.inRange ? root.colorForSlots(modelData.slots, modelData.coverage) : "transparent"
                          border.width: root.selectedDate === modelData.date ? 1 : 0
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

            Row {
              spacing: 4
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
              if (d.files) bits.push(d.files + " file saves")
              if (d.coverage === "git-history-only") bits.push("git history only — may not have happened on this PC")
              if (d.coverage === "unknown") bits.push("not monitored yet")
              if (d.repos && d.repos.length) bits.push(d.repos.join(" · "))
              return bits.join(" · ")
            }
          }

          Text {
            text: "Watching"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
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
            text: "r refreshes · middle-click the bar mark too. GitHub this is not: only folders above, on this machine."
            color: root.dim
            wrapMode: Text.WordWrap
            font.pixelSize: 10
            font.family: root.contentFontFamily
          }
        }
      }
    }
  }
}
