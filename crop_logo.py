#!/usr/bin/env python3
"""
Crop whitespace from LanRED logo
"""
from PIL import Image
import numpy as np

# Input and output paths
input_path = "/home/rutger/Documents/NexusNovus/Projects/4. Raising/bLAN_sWTP_NWL_#8433/11. Financial Model/model/assets/logos/lanred-logo.png"
output_path_1 = input_path  # Save back to original
output_path_2 = "/home/rutger/Documents/Linux Documents/website/nexusnovus/public/logos/lanred-logo.png"

# Read the image
print(f"Reading image from: {input_path}")
img = Image.open(input_path)
print(f"Original size: {img.size}")

# Convert to numpy array
img_array = np.array(img)

# Handle both RGB and RGBA images
if img_array.shape[2] == 4:  # RGBA
    # Consider a pixel as "content" if it's not near-white OR has opacity
    alpha = img_array[:, :, 3]
    rgb = img_array[:, :, :3]
    # Non-white: any RGB channel < 250
    non_white = np.any(rgb < 250, axis=2)
    # Has opacity: alpha > 10
    has_opacity = alpha > 10
    content_mask = non_white & has_opacity
else:  # RGB
    # Non-white: any RGB channel < 250
    content_mask = np.any(img_array < 250, axis=2)

# Find bounding box of content
rows = np.any(content_mask, axis=1)
cols = np.any(content_mask, axis=0)

if not rows.any() or not cols.any():
    print("Error: No content found in image!")
    exit(1)

row_indices = np.where(rows)[0]
col_indices = np.where(cols)[0]

y_min, y_max = row_indices[0], row_indices[-1]
x_min, x_max = col_indices[0], col_indices[-1]

print(f"Content bounding box: ({x_min}, {y_min}) to ({x_max}, {y_max})")

# Add padding
padding = 12
y_min = max(0, y_min - padding)
y_max = min(img_array.shape[0] - 1, y_max + padding)
x_min = max(0, x_min - padding)
x_max = min(img_array.shape[1] - 1, x_max + padding)

print(f"Padded bounding box: ({x_min}, {y_min}) to ({x_max}, {y_max})")

# Crop the image
cropped_img = img.crop((x_min, y_min, x_max + 1, y_max + 1))
print(f"Cropped size: {cropped_img.size}")

# Save to both locations
print(f"Saving to: {output_path_1}")
cropped_img.save(output_path_1, "PNG")

print(f"Saving to: {output_path_2}")
cropped_img.save(output_path_2, "PNG")

print("Done!")
