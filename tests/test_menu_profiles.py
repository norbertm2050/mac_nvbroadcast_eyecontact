"""Exercise the actual Swift profile methods without opening a camera or real config."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swiftc'), 'Requires macOS Swift/AppKit')
class MenuProfileTests(unittest.TestCase):
    def test_profiles_and_switching(self):
        source = (Path(__file__).resolve().parents[1] / 'app/MenuApp.swift').read_text()
        source = source.split('let app = NSApplication.shared')[0]
        start = source.index('    let home = ')
        end = source.index('\n', start)
        source = source[:start] + '    let home = URL(fileURLWithPath:CommandLine.arguments[1])' + source[end:]
        # Replace camera launch only; retain the real switch/stop/refresh code.
        start = source.index('    func start() {')
        end = source.index('    func launch()', start)
        source = source[:start] + '    var testStarts = 0\n    func start() { testStarts += 1 }\n\n' + source[end:]
        source += '''
let app = NSApplication.shared
let test = AppDelegate()
test.item = NSStatusBar.system.statusItem(withLength:NSStatusItem.variableLength)
test.config = ["host":"first.example","port":8554,"token":"first-code","crop_area_percent":60.0]
test.rememberDevice(); test.rememberDevice()
precondition((test.config["devices"] as! [[String:Any]]).count == 1)
test.config["host"]="second.example"; test.config["token"]="second-code"; test.config["device_name"]="Second"
test.rememberDevice(); test.rebuildDevicesMenu()
let profiles=test.config["devices"] as! [[String:Any]]
precondition(profiles.count==2 && profiles[0]["token"] as! String == "first-code")
precondition(test.devicesMenu.items[1].state == .on)
precondition(!test.devicesMenu.items[0].title.contains("code"))
let first=NSMenuItem(); first.representedObject=profiles[0]
test.selectDevice(first)
precondition(test.config["host"] as! String == "first.example" && test.testStarts==0)
let data=try! Data(contentsOf:test.home.appendingPathComponent("config.json"))
let saved=try! JSONSerialization.jsonObject(with:data) as! [String:Any]
precondition(saved["token"] as! String == "first-code")
precondition(saved["crop_area_percent"] as! Double == 60)
let second=NSMenuItem(); second.representedObject=profiles[1]
let worker=Process(); worker.executableURL=URL(fileURLWithPath:"/bin/sleep"); worker.arguments=["10"]
try! worker.run(); test.worker=worker; test.state = .running
test.selectDevice(second)
precondition(test.state == .stopping && test.pendingDevice != nil)
precondition(test.config["host"] as! String == "first.example")
worker.waitUntilExit(); test.refresh()
precondition(test.pendingDevice == nil && test.testStarts==1)
precondition(test.config["host"] as! String == "second.example")
precondition(test.config["token"] as! String == "second-code")
test.state = .stopping; test.rebuildDevicesMenu()
precondition(!test.devicesMenu.items[0].isEnabled)
print("Profile migration, persistence, credential isolation and ordered switching passed")
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swift = root / 'ProfileChecks.swift'
            swift.write_text(source)
            binary = root / 'checks'
            subprocess.run(['swiftc', str(swift), '-o', str(binary), '-framework', 'AppKit', '-framework', 'AVFoundation'], check=True, capture_output=True, timeout=60)
            result = subprocess.run([str(binary), tmp], check=True, capture_output=True, text=True, timeout=30)
            self.assertIn('ordered switching passed', result.stdout)
