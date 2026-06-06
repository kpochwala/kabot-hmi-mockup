with open("frontend/src/components/ui/resizable.tsx", "r") as f:
    content = f.read()

content = content.replace("ref={ref}", "ref={ref as any}")

with open("frontend/src/components/ui/resizable.tsx", "w") as f:
    f.write(content)
