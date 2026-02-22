#!/usr/bin/env python3
"""用 ApplicationServices 找 Python 視窗中所有 UI 元素的位置"""
import subprocess
import json

# 用 swift 直接查 accessibility tree
swift_code = r'''
import Cocoa
import ApplicationServices

func getElementInfo(_ element: AXUIElement, depth: Int = 0, maxDepth: Int = 8) -> [[String: Any]] {
    var results: [[String: Any]] = []
    if depth > maxDepth { return results }
    
    var role: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &role)
    let roleStr = (role as? String) ?? "unknown"
    
    var position: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXPositionAttribute as CFString, &position)
    var pos = CGPoint.zero
    if let posVal = position {
        AXValueGetValue(posVal as! AXValue, .cgPoint, &pos)
    }
    
    var size: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXSizeAttribute as CFString, &size)
    var sz = CGSize.zero
    if let szVal = size {
        AXValueGetValue(szVal as! AXValue, .cgSize, &sz)
    }
    
    var titleRef: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXTitleAttribute as CFString, &titleRef)
    let title = (titleRef as? String) ?? ""
    
    var valueRef: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &valueRef)
    let value = (valueRef as? String) ?? ""
    
    var descRef: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &descRef)
    let desc = (descRef as? String) ?? ""
    
    let info: [String: Any] = [
        "role": roleStr,
        "x": Int(pos.x),
        "y": Int(pos.y),
        "w": Int(sz.width),
        "h": Int(sz.height),
        "title": title,
        "value": value,
        "desc": desc,
        "depth": depth
    ]
    results.append(info)
    
    var children: CFTypeRef?
    AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &children)
    if let kids = children as? [AXUIElement] {
        for kid in kids {
            results.append(contentsOf: getElementInfo(kid, depth: depth + 1, maxDepth: maxDepth))
        }
    }
    
    return results
}

let apps = NSWorkspace.shared.runningApplications.filter { $0.localizedName == "Python" }
guard let app = apps.first else {
    print("Python app not found")
    exit(1)
}

let appElement = AXUIElementCreateApplication(app.processIdentifier)
let allElements = getElementInfo(appElement, depth: 0, maxDepth: 10)

// Filter to interesting elements (combo boxes, buttons, popups, or elements with y > 350)
for elem in allElements {
    let role = elem["role"] as! String
    let y = elem["y"] as! Int
    let x = elem["x"] as! Int
    let w = elem["w"] as! Int
    let h = elem["h"] as! Int
    let title = elem["title"] as! String
    let value = elem["value"] as! String
    let depth = elem["depth"] as! Int
    
    if role.contains("ComboBox") || role.contains("PopUp") || role.contains("MenuButton") ||
       (y >= 380 && y <= 430 && w > 20) ||
       title.lowercased().contains("region") || value.lowercased().contains("region") ||
       value.contains("us-east") || value.contains("us-west") || value.contains("Nova") ||
       title.contains("摘要") || title.contains("模型") || title.contains("儲存") {
        let indent = String(repeating: "  ", count: depth)
        print("\(indent)\(role) pos:(\(x),\(y)) size:(\(w)x\(h)) title:'\(title)' value:'\(value)'")
    }
}
'''

result = subprocess.run(["swift", "-e", swift_code], capture_output=True, text=True, timeout=15)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])
