import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "bjcatar.garden"

  readonly property var last7: panelLoader.item ? panelLoader.item.last7 : []
  readonly property int dataRev: panelLoader.item ? panelLoader.item.dataRev : 0
  readonly property int todaySlots: panelLoader.item ? panelLoader.item.todaySlots : 0

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
  function open() { if (panelLoader.item && panelLoader.item.open) panelLoader.item.open() }
  function close() { if (panelLoader.item && panelLoader.item.close) panelLoader.item.close() }
  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false
  function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }

  function cellColor(slots, coverage) {
    if (panelLoader.item && panelLoader.item.colorForSlots)
      return panelLoader.item.colorForSlots(slots, coverage)
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

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    slotSize: Style.bar.iconSlot
    tooltipText: root.todaySlots <= 0
      ? "No activity on this PC today"
      : (HeatmapHours + " on this PC today")
    iconComponent: weekMark

    onPressed: function(b) {
      if (b === Qt.MiddleButton) root.refresh()
      else root.togglePanel()
    }
  }

  readonly property string HeatmapHours: {
    var h = root.todaySlots * 0.5
    if (h === 1) return "1 hour"
    if (h === Math.floor(h)) return h + " hours"
    return h + " hours"
  }

  Component {
    id: weekMark
    Item {
      Row {
        anchors.centerIn: parent
        spacing: 1
        Repeater {
          model: 7
          Rectangle {
            required property int index
            width: 2
            height: 7
            radius: 0
            color: {
              var _ = root.dataRev
              var day = root.last7[index]
              return root.cellColor(day ? day.slots : 0, day ? day.coverage : "empty")
            }
          }
        }
      }
    }
  }
}
