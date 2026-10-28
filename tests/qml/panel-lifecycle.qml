import QtQuick
import Quickshell
import qs.Ui
import "./garden" as Garden
ShellRoot {
  PluginBarApi {
    id: api
    pluginId: "bjcatar.garden"
    moduleName: "bjcatar.garden"
    foreground: "white"
    fontFamily: "monospace"
    _setCenterHoverRevealSuppressed: value => { api._centerHoverRevealSuppressed = value }
  }
  PluginBarApi {
    id: apiB
    pluginId: "bjcatar.garden.b"
    moduleName: "bjcatar.garden.b"
    foreground: "white"
    fontFamily: "monospace"
    _setCenterHoverRevealSuppressed: value => { apiB._centerHoverRevealSuppressed = value }
  }
  Garden.Panel {
    id: garden
    bar: api
    firstScanDone: true
  }
  Garden.Panel {
    id: other
    bar: apiB
    firstScanDone: true
  }
  Timer {
    interval: 100
    running: true
    onTriggered: {
      // Keep every layer surface unmapped while exercising the real component.
      function unmap(panel) {
        var window = null
        for (var i = 0; i < panel.data.length; i++) {
          var node = panel.data[i]
          if ("focusPrimed" in node) {
            node.open = false
            window = node
          }
        }
        if (!window) throw new Error("Cannot isolate panel window")
        return window
      }
      var child = unmap(garden)
      var otherWindow = unmap(other)
      function check(value, message) {
        if (!value) throw new Error(message)
      }
      try {
        garden.open()
        check(garden.opened, "Did not open")
        check(api.centerHoverRevealSuppressed, "Public setter was not used")
        garden.close()
        check(!garden.opened, "Did not close")
        check(!api.centerHoverRevealSuppressed, "Bar state was not cleared")

        garden.toggle()
        check(garden.opened, "Toggle did not open")
        garden.toggle()
        check(!garden.opened, "Toggle did not close")

        garden.open()
        child = null
        for (var i = 0; i < garden.data.length; i++) {
          if ("focusPrimed" in garden.data[i]) child = garden.data[i]
        }
        child.contentItem[0].closeRequested()
        check(!garden.opened, "Key catcher dismissal did not close")

        garden.open()
        child.close()
        check(!garden.opened, "Outside-click close route did not close")

        api._setCenterHoverRevealSuppressed = function(value) {
          if (!value) {
            check(!garden.opened, "Cleanup ran before hide")
            throw new Error("injected cleanup failure")
          }
        }
        garden.open()
        garden.close()
        check(!garden.opened, "Cleanup failure prevented closing")

        api._setCenterHoverRevealSuppressed = function(value) {
          throw new Error("injected setter failure")
        }
        garden.open()
        check(garden.opened, "Setter failure prevented opening")
        garden.close()
        check(!garden.opened, "Setter failure prevented closing")

        api._setCenterHoverRevealSuppressed = function(value) {
          api._centerHoverRevealSuppressed = value
        }
        garden.open()
        other.open()
        check(garden.opened && other.opened, "Both monitors should open")
        garden.close()
        check(!garden.opened, "First monitor stayed open")
        check(other.opened, "Closing one monitor closed the other")
        check(!api.centerHoverRevealSuppressed, "Closed monitor left hover suppressed")
        check(apiB.centerHoverRevealSuppressed, "Closing one monitor cleared the other bar")
        other.close()
        check(!other.opened, "Other monitor stayed open before the burst")
        for (var n = 0; n < 6; n++) {
          garden.toggle()
          other.toggle()
        }
        check(!garden.opened, "Rapid reopen left the panel open")
        check(!other.opened, "Rapid reopen left the other monitor open")
        check(!api.centerHoverRevealSuppressed, "Rapid close left hover suppressed")
        check(!apiB.centerHoverRevealSuppressed, "Rapid close left the other bar suppressed")

        garden.open()
        child.contentItem[0].closeRequested()
        check(!garden.opened, "Escape route failed after reopen")
        garden.open()
        child.close()
        check(!garden.opened, "Outside-click close failed after reopen")
        other.open()
        other.toggle()
        check(!other.opened, "Sprout toggle failed after reopen")

        child.open = Qt.binding(function() { return garden.opened })
        otherWindow.open = Qt.binding(function() { return other.opened })
        check(!child.open, "KeyboardPanel stayed open after dismiss")
        check(!otherWindow.open, "Other KeyboardPanel stayed open after dismiss")
        check(!child.focusPrimed, "Exclusive prime stayed latched")
        check(!otherWindow.focusPrimed, "Other Exclusive prime stayed latched")
        console.log("GARDEN_TEST_PASS")
      } catch (e) {
        console.error("GARDEN_TEST_FAIL", e)
      }
      Qt.quit()
    }
  }
}
