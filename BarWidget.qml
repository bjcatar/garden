import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "bjcatar.garden"

  readonly property var last7: panelLoader.item ? panelLoader.item.last7 : []
  readonly property int dataRev: panelLoader.item ? panelLoader.item.dataRev : 0
  readonly property int todayCount: panelLoader.item ? panelLoader.item.todayCount : 0

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function refresh() {
    if (panelLoader.item && panelLoader.item.refresh) panelLoader.item.refresh()
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.open) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  function cellColor(commits) {
    if (panelLoader.item && panelLoader.item.colorForCount)
      return panelLoader.item.colorForCount(commits)
    return Util.alpha(bar ? bar.foreground : Color.foreground, 0.14)
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  IpcHandler {
    target: "bjcatar.garden"
    function refresh(): void { root.refresh() }
    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.togglePanel() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: root.todayCount === 1 ? "1 contribution today" : (root.todayCount + " contributions today")
    hasVisualContent: true
    horizontalMargin: 8
    verticalPadding: 8
    fixedWidth: strip.implicitWidth + 16

    onPressed: function(b) {
      if (b === Qt.MiddleButton) root.refresh()
      else root.togglePanel()
    }

    Row {
      id: strip
      anchors.centerIn: parent
      spacing: 2

      Repeater {
        model: 7
        Rectangle {
          required property int index
          width: 5
          height: 5
          radius: 1
          color: {
            var _ = root.dataRev
            var day = root.last7[index]
            return root.cellColor(day ? day.commits : 0)
          }
        }
      }
    }
  }
}
