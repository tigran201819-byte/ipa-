import sys
import os

app_name = sys.argv[1]
bundle_id = sys.argv[2]

os.makedirs("Sources", exist_ok=True)

swift_code = '''import UIKit
import WebKit

@main
class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = MainViewController()
        window?.makeKeyAndVisible()
        return true
    }
}

class MainViewController: UIViewController {
    var webView: WKWebView!

    override var preferredStatusBarStyle: UIStatusBarStyle {
        return .lightContent
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        
        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.backgroundColor = .black
        webView.isOpaque = false
        view.addSubview(webView)

        startPythonEngine()

        if let htmlPath = Bundle.main.path(forResource: "index", ofType: "html", inDirectory: "app_code") {
            let url = URL(fileURLWithPath: htmlPath)
            webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
    }

    func startPythonEngine() {
        guard let resourcePath = Bundle.main.resourcePath else { return }
        let appCodePath = resourcePath + "/app_code"
        let frameworkPath = resourcePath + "/Frameworks/Python.framework"
        
        setenv("PYTHONHOME", frameworkPath, 1)
        setenv("PYTHONPATH", "\\(appCodePath):\\(appCodePath)/site-packages", 1)
        
        DispatchQueue.global(qos: .userInitiated).async {
            Py_Initialize()
            let script = """
            import sys, os
            os.chdir('\\(appCodePath)')
            import main
            """
            PyRun_SimpleString(script)
        }
    }
}
'''

bridging_header = '''#import <Python/Python.h>
'''

info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>{app_name}</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>$(PRODUCT_NAME)</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSRequiresIPhoneOS</key>
    <true/>
    <key>UIUserInterfaceStyle</key>
    <string>Dark</string>
    <key>UILaunchScreen</key>
    <dict/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
'''

with open("Sources/App.swift", "w") as f:
    f.write(swift_code)

with open("Sources/Bridging-Header.h", "w") as f:
    f.write(bridging_header)

with open("Sources/Info.plist", "w") as f:
    f.write(info_plist)

project_yml = f'''name: {app_name}
options:
  bundleIdPrefix: com.custom
targets:
  {app_name}:
    type: application
    platform: iOS
    deploymentTarget: "15.0"
    sources:
      - path: Sources
        excludes:
          - Info.plist
      - path: app_code
        type: folder
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {bundle_id}
        SWIFT_OBJC_BRIDGING_HEADER: Sources/Bridging-Header.h
        INFOPLIST_FILE: Sources/Info.plist
        GENERATE_INFOPLIST_FILE: NO
        ENABLE_BITCODE: NO
        CODE_SIGNING_ALLOWED: NO
    dependencies:
      - framework: Frameworks/Python.xcframework
        embed: true
'''

with open("project.yml", "w") as f:
    f.write(project_yml)
