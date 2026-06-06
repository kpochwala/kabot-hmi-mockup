with open("frontend/src/components/ui/resizable.tsx", "r") as f:
    content = f.read()

new_panel = """import React from "react"
const ResizablePanel = React.forwardRef<any, ResizablePrimitive.PanelProps>(({ ...props }, ref) => {
  return <ResizablePrimitive.Panel ref={ref} data-slot="resizable-panel" {...props} />
})
"""
content = content.replace(
"""function ResizablePanel({ ...props }: ResizablePrimitive.PanelProps) {
  return <ResizablePrimitive.Panel data-slot="resizable-panel" {...props} />
}""", new_panel)

with open("frontend/src/components/ui/resizable.tsx", "w") as f:
    f.write(content)
