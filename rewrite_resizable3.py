with open("frontend/src/components/ui/resizable.tsx", "r") as f:
    content = f.read()

content = content.replace("return <ResizablePrimitive.Panel ref={ref as any} data-slot=\\"resizable-panel\\" {...props} />",
"// @ts-ignore\\n  return <ResizablePrimitive.Panel ref={ref} data-slot=\\"resizable-panel\\" {...props} />")

with open("frontend/src/components/ui/resizable.tsx", "w") as f:
    f.write(content)
