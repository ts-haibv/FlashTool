import os
from PIL import Image, ImageDraw

def apply_rounded_corners():
    brain_img_path = '/home/haibachvan/.gemini/antigravity/brain/32551d71-db34-435b-8ed7-d8b2e465bf2c/flashtool_icon_1775579064961.png'
    output_path = '/home/haibachvan/Workspace/FlashTool/assets/icon.png'
    
    img = Image.open(brain_img_path).convert("RGBA")
    w, h = img.size
    
    # Create an anti-aliased mask the same size as the image
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw a rounded rectangle on the mask
    # A standard iOS-like squircle corner radius is ~17.5% of width.
    # 640 * 0.175 = ~112px
    r = 112
    draw.rounded_rectangle((0, 0, w, h), radius=r, fill=255)
    
    # Apply the mask to the image alpha channel
    mask_data = mask.getdata()
    img_data = img.getdata()
    new_data = []
    
    for (img_pixel, mask_pixel) in zip(img_data, mask_data):
        if mask_pixel == 0:
            new_data.append((255, 255, 255, 0)) # Fully transparent for outside corners
        else:
            new_data.append((img_pixel[0], img_pixel[1], img_pixel[2], min(img_pixel[3], mask_pixel)))
            
    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"✅ Successfully created perfect rounded icon at {output_path} with size {w}x{h}")

if __name__ == '__main__':
    apply_rounded_corners()
