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
  Garden.Panel {
    id: garden
    bar: api
    firstScanDone: true
  }
  Timer {
    interval: 100
    running: true
    onTriggered: {
      // Keep every layer surface unmapped while exercising the real component.
      var found = false
      for (var i = 0; i < garden.data.length; i++) {
        var child = garden.data[i]
        if ("focusPrimed" in child) {
          child.open = false
          found = true
        }
      }
      if (!found) throw new Error("Cannot isolate panel window")
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
        for (i = 0; i < garden.data.length; i++) {
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
        console.log("GARDEN_TEST_PASS")
      } catch (e) {
        console.error("GARDEN_TEST_FAIL", e)
      }
      Qt.quit()
    }
  }
}
