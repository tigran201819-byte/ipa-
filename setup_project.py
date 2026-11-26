import sys
import os
import json
import glob

app_name = sys.argv[1]
bundle_id = sys.argv[2]

os.makedirs("Sources", exist_ok=True)
os.makedirs("Assets.xcassets/AppIcon.appiconset", exist_ok=True)

icon_contents = {
    "images": [
        {
            "filename": "icon-1024.png",
            "idiom": "universal",
            "platform": "ios",
            "size": "1024x1024"
        }
    ],
    "info": {
        "author": "xcode",
        "version": 1
    }
}

# Ищет любой файл icon.* (включая icon.png.png, icon.jpeg.jpeg и т.д.)
found_icons = glob.glob("app_code/icon.*")
if found_icons:
    src = found_icons[0]
    os.system(f'sips -s format png -z 1024 1024 "{src}" --out Assets.xcassets/AppIcon.appiconset/icon-1024.png')
    os.system(f'sips -s format png -z 180 180 "{src}" --out app_code/AppIcon60x60@3x.png')

with open("Assets.xcassets/AppIcon.appiconset/Contents.json", "w") as f:
    json.dump(icon_contents, f, indent=2)

with open("Assets.xcassets/Contents.json", "w") as f:
    json.dump({"info": {"author": "xcode", "version": 1}}, f, indent=2)

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
        view.backgroundColor = UIColor(red: 0.05, green: 0.03, blue: 0.11, alpha: 1.0)

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        
        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.backgroundColor = UIColor(red: 0.05, green: 0.03, blue: 0.11, alpha: 1.0)
        webView.isOpaque = false
        view.addSubview(webView)

        if let htmlPath = Bundle.main.path(forResource: "index", ofType: "html", inDirectory: "app_code") {
            let url = URL(fileURLWithPath: htmlPath)
            webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        }
    }
}
'''

info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>ru</string>
    <key>CFBundleDisplayName</key>
    <string>{app_name}</string>
    <key>CFBundleExecutable</key>
    <string>$(EXECUTABLE_NAME)</string>
    <key>CFBundleIdentifier</key>
    <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
    <key>CFBundleIconFiles</key>
    <array>
        <string>AppIcon60x60</string>
    </array>
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
</dict>
</plist>
'''

with open("Sources/App.swift", "w", encoding="utf-8") as f:
    f.write(swift_code)

with open("Sources/Info.plist", "w", encoding="utf-8") as f:
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
      - path: Assets.xcassets
      - path: app_code
        type: folder
    settings:
      base:
        PRODUCT_BUNDLE_IDENTIFIER: {bundle_id}
        INFOPLIST_FILE: Sources/Info.plist
        ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon
        GENERATE_INFOPLIST_FILE: NO
        ENABLE_BITCODE: NO
        CODE_SIGNING_ALLOWED: NO
'''

with open("project.yml", "w", encoding="utf-8") as f:
    f.write(project_yml)
