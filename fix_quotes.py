with open('frontend/src/app/page.tsx', 'r') as f:
    content = f.read()
content = content.replace("style={{ backgroundColor: focusedChannel ? \\`\\${focusedChannel.color}15` : 'transparent' }}", "style={{ backgroundColor: focusedChannel ? `${focusedChannel.color}15` : 'transparent' }}")
content = content.replace("style={{ backgroundColor: focusedChannel ? `\\${focusedChannel.color}15` : 'transparent' }}", "style={{ backgroundColor: focusedChannel ? `${focusedChannel.color}15` : 'transparent' }}")
content = content.replace("style={{ backgroundColor: focusedChannel ? \\`\\${focusedChannel.color}15\\` : 'transparent' }}", "style={{ backgroundColor: focusedChannel ? `${focusedChannel.color}15` : 'transparent' }}")

with open('frontend/src/app/page.tsx', 'w') as f:
    f.write(content)
