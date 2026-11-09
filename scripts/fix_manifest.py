import re, sys

path = r"E:\Users\Ninja hp LAPTOP\Documents\deepseek-harness\default-workspace\manifest.xml"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

orig = content

# 1. Remove target-level="legacy" from root <manifest ...> element
content = content.replace(
    '<manifest version="1.0" type="device" target-level="legacy">',
    '<manifest version="1.0" type="device">'
)

# 2. Add interface to android.hardware.renderscript HAL (currently interface-less)
rs_before = '''    <hal format="hidl">
        <name>android.hardware.renderscript</name>
        <transport arch="32+64">passthrough</transport>
        <version>1.0</version>
    </hal>'''
rs_after = '''    <hal format="hidl">
        <name>android.hardware.renderscript</name>
        <transport arch="32+64">passthrough</transport>
        <version>1.0</version>
        <interface>
            <name>IDevice</name>
            <instance>default</instance>
        </interface>
        <fqname>@1.0::IDevice/default</fqname>
    </hal>'''
if rs_before in content:
    content = content.replace(rs_before, rs_after)
    print("renderscript interface: PATCHED")
else:
    print("renderscript interface: NOT FOUND (check indentation)")

# 3. Remove the duplicate cas fragment reference? We cannot edit the fragment from here,
#    but we can drop the duplicate cas@1.0 entry from the main manifest so the fragment's
#    1.1 is the only declaration. Actually keep 1.0 in main (it has fqname) and the fragment
#    has 1.1; duplicates are merged by version normally. Leave as-is for now; note it.

print("target-level removed:", 'target-level' not in content)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# print a short diff of changed lines
import difflib
diff = list(difflib.unified_diff(orig.splitlines(), content.splitlines(), lineterm="", n=1))
print("\n".join(diff))
