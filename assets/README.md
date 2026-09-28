# Application icon

`icon.png` was created with the built-in image generation tool for this project. `AppIcon.icns` and `AppIcon.ico` contain resized representations of that same artwork. No third-party brand mark is used.

Final prompt:

> Create one finished 1024x1024 square production app icon for Remote Eye Contact, a desktop webcam gaze correction app. Use case logo-brand. One original bold geometric eye with a centered camera-lens pupil, friendly, calm, precise, subtle polished depth, readable at 32 pixels. Center the single mark inside a rounded-square desktop app tile with generous safe margins; transparent outside the tile. Elegant restrained colors of your choice. Straight-on final icon artwork only, no mockup, no text or letters, no watermark, no multiple variants. Do not imitate NVIDIA or any existing brand logo.

To regenerate the platform containers from the original PNG (macOS):

```sh
swift scripts/build-icons.swift assets/icon.png assets
iconutil -c icns assets/AppIcon.iconset -o assets/AppIcon.icns
```
