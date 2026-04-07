from PIL import Image

def remove_checkerboard():
    brain_path = '/home/haibachvan/.gemini/antigravity/brain/32551d71-db34-435b-8ed7-d8b2e465bf2c/flashtool_icon_transparent_1775583222050.png'
    output_path = '/home/haibachvan/Workspace/FlashTool/assets/icon.png'
    
    img = Image.open(brain_path).convert('RGBA')
    pixels = img.load()
    w, h = img.size
    
    # 1. Detect background colors exactly by sampling the corners
    # A checkerboard usually has exactly 2 colors. Let's find them from the first 50x50 pixels:
    bg_colors = set()
    for y in range(40):
        for x in range(40):
            r, g, b, a = pixels[x, y]
            # Saturated/colored pixels are not checkerboard
            if abs(r - g) < 20 and abs(g - b) < 20 and abs(r - b) < 20:
                bg_colors.add((r, g, b))
    
    # We allow a small tolerance because JPG artifacts might shift it
    def is_checkerboard(color):
        r, g, b, a = color
        for bgr, bgg, bgb in bg_colors:
            if abs(r - bgr) < 25 and abs(g - bgg) < 25 and abs(b - bgb) < 25:
                return True
        return False

    # 2. Convert matches to transparent
    removed_count = 0
    for y in range(h):
        for x in range(w):
            if is_checkerboard(pixels[x, y]):
                pixels[x, y] = (0, 0, 0, 0)
                removed_count += 1
                
    img.save(output_path, 'PNG')
    print(f"✅ Removed {removed_count} pixels of checkerboard background")
    
    # 3. Generate all sizes
    sizes = [48, 64, 128, 256]
    for size in sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(f'/home/haibachvan/Workspace/FlashTool/assets/icon_{size}.png', 'PNG')
    
    # Create ICO
    img.save('/home/haibachvan/Workspace/FlashTool/assets/icon.ico', format='ICO', sizes=[(s,s) for s in sizes])
    print('✅ Generated all sub-sizes successfully')

if __name__ == '__main__':
    remove_checkerboard()
