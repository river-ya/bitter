from PIL import Image, ImageDraw, ImageFilter
import math

size = 128
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

center = size // 2
outer_radius = 50
inner_radius = 20

draw.ellipse([center - outer_radius, center - outer_radius, 
              center + outer_radius, center + outer_radius], 
             fill=(255, 255, 255, 255), outline=(50, 50, 50, 255), width=3)

draw.ellipse([center - inner_radius, center - inner_radius, 
              center + inner_radius, center + inner_radius], 
             fill=(50, 50, 50, 255))

arrow_length = 30
arrow_width = 12

draw.polygon([
    (center + inner_radius + 8, center),
    (center + inner_radius + arrow_length, center - arrow_width),
    (center + inner_radius + arrow_length, center + arrow_width)
], fill=(255, 255, 255, 255))

draw.polygon([
    (center - inner_radius - 8, center),
    (center - inner_radius - arrow_length, center - arrow_width),
    (center - inner_radius - arrow_length, center + arrow_width)
], fill=(255, 255, 255, 255))

shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
shadow_draw = ImageDraw.Draw(shadow)
shadow_draw.ellipse([center - outer_radius + 3, center - outer_radius + 3, 
                     center + outer_radius + 3, center + outer_radius + 3], 
                    fill=(0, 0, 0, 30))

img = Image.alpha_composite(shadow, img)

img.save('c:/Users/90617/Desktop/bitter_camera/images/switch-camera_new.png')
print("Image created successfully!")
