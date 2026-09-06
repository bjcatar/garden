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
  property int dataRev: 0
  property var last7: []
  property var weeks: []
  property var cuts: [1, 2, 4]
  property var monthLabels: []
  property string selectedDate: ""
  property int yearIndex: 0

  readonly property int todayCount: (snapshot.today && snapshot.today.commits) ? snapshot.today.commits : 0
  readonly property int total: snapshot.total || 0
  readonly property var years: snapshot.years || []
  readonly property var selectedEntries: Heatmap.entriesFor(snapshot, selectedDate)

  readonly property int cell: 10
  readonly property int gap: 2
  readonly property int labelW: 28
  readonly property int monthH: 16

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  function colorForLevel(level) {
    if (level <= 0) return alpha(contentForeground, 0.12)
    var mix = [0, 0.28, 0.48, 0.72, 1][Math.min(4, level)]
    return Qt.rgba(accent.r, accent.g, accent.b, mix)
  }

  function colorForCount(commits) {
    return colorForLevel(Heatmap.levelFor(commits || 0, cuts))
  }

  function applySnapshot(parsed) {
    snapshot = parsed && typeof parsed === "object" ? parsed : {}
    var range = snapshot.range || {}
    var days = snapshot.days || {}
    var end = range.end || Qt.formatDate(new Date(), "yyyy-MM-dd")
    var start = range.start || end
    weeks = Heatmap.buildWeeks(start, end, days)
    monthLabels = Heatmap.monthLabels(weeks)
    last7 = Heatmap.lastNDays(end, 7, days)
    var counts = []
    for (var w = 0; w < weeks.length; w++) {
      for (var d = 0; d < weeks[w].length; d++) {
        if (weeks[w][d].inRange) counts.push(weeks[w][d].commits)
      }
    }
    cuts = Heatmap.cutsFromCounts(counts)
    dataRev++
  }

  function refresh() {
    if (!scanProc.running) scanProc.running = true
  }

  function open() {
    refresh()
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

  function scanPath() {
    var url = Qt.resolvedUrl("bin/garden-scan").toString()
    return url.replace(/^file:\/\//, "")
  }

  FileView {
    id: dataFile
    path: Quickshell.env("HOME") + "/.local/state/omarchy/garden/heatmap.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        root.applySnapshot(JSON.parse(String(text() || "{}")))
      } catch (e) {
        console.warn("garden", "bad heatmap.json", e)
      }
    }
  }

  Process {
    id: scanProc
    command: ["python3", root.scanPath()]
  }

  Timer {
    interval: 900000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(720))
    contentHeight: panel.fittedContentHeight(body.implicitHeight, Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onActivateRequested: root.refresh()
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
          spacing: Style.space(12)
          leftPadding: Style.space(16)
          rightPadding: Style.space(16)
          topPadding: Style.space(14)
          bottomPadding: Style.space(16)

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: root.total === 1
              ? "1 contribution in the last year"
              : (root.total + " contributions in the last year")
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.body
            font.bold: true
          }

          Text {
            width: parent.width - parent.leftPadding - parent.rightPadding
            visible: repoLine.text !== ""
            id: repoLine
            text: {
              var _ = root.dataRev
              var repos = root.snapshot.repos || []
              var bits = []
              for (var i = 0; i < repos.length; i++) {
                if (repos[i].commits > 0)
                  bits.push(repos[i].name + " (" + repos[i].commits + ")")
              }
              return bits.join(" · ")
            }
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          // Heatmap + year rail
          Row {
            spacing: Style.space(12)

            Column {
              spacing: Style.space(4)

              Item {
                width: root.labelW + root.weeks.length * (root.cell + root.gap)
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
                spacing: 0

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
                          color: modelData.inRange ? root.colorForCount(modelData.commits) : "transparent"
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
                              text: modelData.commits + (modelData.commits === 1 ? " contribution on " : " contributions on ") + Heatmap.prettyDate(modelData.date)
                              fontFamily: root.contentFontFamily
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
                layoutDirection: Qt.RightToLeft
                width: root.labelW + root.weeks.length * (root.cell + root.gap)
                Text { text: "More"; color: root.dim; font.pixelSize: 10; font.family: root.contentFontFamily }
                Repeater {
                  model: 5
                  Rectangle {
                    required property int index
                    width: root.cell
                    height: root.cell
                    radius: 2
                    color: root.colorForLevel(4 - index)
                  }
                }
                Text { text: "Less"; color: root.dim; font.pixelSize: 10; font.family: root.contentFontFamily }
              }
            }
          }

          Text {
            text: "Contribution activity"
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: true
          }

          Text {
            visible: root.selectedDate === ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            text: "Click a day to see what landed on this machine."
            color: root.dim
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
            wrapMode: Text.WordWrap
          }

          Column {
            visible: root.selectedDate !== ""
            width: parent.width - parent.leftPadding - parent.rightPadding
            spacing: Style.space(6)

            Text {
              text: root.selectedDate !== "" ? Heatmap.prettyDate(root.selectedDate) : ""
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Repeater {
              model: root.selectedEntries
              Column {
                required property var modelData
                width: parent.width
                spacing: 1
                Text {
                  width: parent.width
                  text: modelData.hash.slice(0, 7) + "  " + modelData.subject
                  color: root.contentForeground
                  font.family: root.contentFontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }
                Text {
                  width: parent.width
                  text: modelData.repo + "  +" + modelData.additions + " / −" + modelData.deletions
                  color: root.dim
                  font.family: root.contentFontFamily
                  font.pixelSize: 10
                  elide: Text.ElideRight
                }
              }
            }

            Text {
              visible: root.selectedDate !== "" && root.selectedEntries.length === 0
              text: "Quiet day — no commits matched."
              color: root.dim
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }
      }
    }
  }
}
