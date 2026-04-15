# parse the svg file and get the path data

import os
import json
import xml.etree.ElementTree as ET


# Function to find the target structure
def find_target_group(root: ET.Element) -> tuple[list[ET.Element], list[ET.Element]]:
    gs, paths = [], []
    namespace = "http://www.w3.org/2000/svg"
    for g in root.findall("{%s}g" % namespace):
        if "fill" in g.attrib:  # Step 1: Check for <g fill>
            for sub_g in g.findall("{%s}g" % namespace):  # Step 2: Check for <g transform>
                if "transform" in sub_g.attrib:
                    path = sub_g.find(".//{%s}path" % namespace)  # Step 4: <path> inside
                    if path is not None:
                        gs.append(g)
                        paths.append(path)

    return gs, paths  # Return both elements


# Function to find the target structure
def find_circle_group(root: ET.Element) -> tuple[list[ET.Element], list[ET.Element]]:
    gs, paths = [], []
    namespace = "http://www.w3.org/2000/svg"
    for g in root.findall("{%s}g" % namespace):
        circle = g.find(".//{%s}circle" % namespace)  # Step 4: <path> inside
        if circle is not None:
            gs.append(g)
            paths.append(circle)

    return gs, paths  # Return both elements


# Function to parse the SVG file and get the target group and path
def parse_svg(svg_path) -> ET.ElementTree:
    # Check if file exists
    if not os.path.isfile(svg_path):
        print(f'WARNING: "{svg_path}" not found!')
        return None

    # Set prefix to avoid namespace
    ET.register_namespace("", "http://www.w3.org/2000/svg")

    # Load SVG
    return ET.parse(svg_path)


# Create a json file with the path data to create numbers
def read_out_numbers_of_file(svg_image_path: str):
    # Parse the SVG file
    tree = parse_svg(svg_image_path)
    root = tree.getroot()
    target_groups, target_paths = find_target_group(root)

    # Write each path in target_path into a json file called "numbers.json", labeled with the corresponding index
    dict_path = {}
    for i, path in enumerate(target_paths):
        dict_path[i] = path.attrib["d"]
    with open("numbers.json", "w") as file:
        json.dump(dict_path, file, indent=4)


# Visually change the channel number of the electrode
def change_number_to(svg_image_path: str, electrode_nb: int, new_number: int) -> str:
    # Parse the SVG file
    tree = parse_svg(svg_image_path)
    root = tree.getroot()
    target_groups, target_paths = find_target_group(root)

    # Load numbers.json
    with open("numbers.json", "r") as file:
        data = json.load(file)

    # Change the path data to new path data from data
    if len(target_paths) > electrode_nb:
        target_paths[electrode_nb].attrib["d"] = data[f"{new_number}"]

    # Create absolute path to save the modified image
    modified_file_path = os.path.join(os.getcwd(), "gui/images/svg_images/modified_image.svg")

    # Write the parsed file to a new svg file
    tree.write(modified_file_path)

    return modified_file_path

def change_label_to(svg_image_path: str, electrode_nb: int, label: str, fill: str = "#FFFFFF", y_nudge: float = 4.0) -> str:
    """
    Write a full text label (e.g., 'L1', 'M1', 'R2') centered on the electrode index.
    Uses the circle center for positioning and adds a <text> element in the same group.
    """
    tree = parse_svg(svg_image_path)
    root = tree.getroot()

    # Find electrode groups/circles to get positions
    circle_groups, circle_nodes = find_circle_group(root)
    target_groups, _ = find_target_group(root)

    if electrode_nb < 0 or electrode_nb >= len(target_groups):
        return svg_image_path

    # Prefer circle center if available
    cx = cy = None
    if electrode_nb < len(circle_nodes):
        c = circle_nodes[electrode_nb]
        cx = c.get("cx")
        cy = c.get("cy")

    # Fallback to place at (0,0) if no circle info (will likely be transformed by parent group)
    if cx is None or cy is None:
        cx, cy = "0", "0"
    
    # Apply tiny downward adjustment
    try:
        cy_val = float(cy)
        cy_adj = f"{cy_val + y_nudge:.2f}"
    except Exception:
        cy_adj = cy  # fallback without adjustment if numeric conversion fails

    g = target_groups[electrode_nb]

    # Remove any previous label we added
    to_remove = []
    for child in list(g):
        if child.tag.endswith("text") and child.get("data-electrode-label") == "true":
            to_remove.append(child)
    for node in to_remove:
        g.remove(node)

    # Remove any previous label we added
    to_remove = []
    for child in list(g):
        if child.tag.endswith("text") and child.get("data-electrode-label") == "true":
            to_remove.append(child)
    for node in to_remove:
        g.remove(node)

    # Create a centered text node
    txt = ET.Element("text")
    txt.set("x", str(cx))
    txt.set("y", str(cy_adj))
    txt.set("fill", fill)
    txt.set("font-size", "22")
    txt.set("font-weight", "700")
    txt.set("font-family", "Arial")
    txt.set("text-anchor", "middle")
    txt.set("dominant-baseline", "middle")
    txt.set("data-electrode-label", "true")
    txt.text = str(label)

    g.append(txt)

    # Write back and return path
    tree.write(svg_image_path, encoding="utf-8", xml_declaration=True)
    return svg_image_path


# Visually change the color of the number
def change_color_to(svg_image_path: str, group_nb: int, new_color: str, is_back=True) -> str:
    # Parse the SVG file
    tree = parse_svg(svg_image_path)
    root = tree.getroot()
    target_groups, target_paths = find_target_group(root)

    # Change the color in target group to a new color
    if len(target_groups) > group_nb:
        if is_back:
            target_groups[group_nb].attrib["fill"] = new_color
        else:
            # Reduce the target groups to uniques
            target_groups = list(dict.fromkeys(target_groups))
            target_groups[group_nb].attrib["fill"] = new_color

    # Create absolute path to save the modified image
    if is_back:
        modified_file_path = os.path.join(os.getcwd(), "gui/images/svg_images/modified_image.svg")
    else:
        modified_file_path = os.path.join(os.getcwd(), "gui/images/svg_images/modified_para_image.svg")

    # Write the parsed file to a new svg file
    tree.write(modified_file_path)

    return modified_file_path

# Change the color of the circle (!!! OVERWRITE THE IMAGE !!!)
def change_circle_color_to(svg_image_path: str, group_nb: int, new_color: str) -> None:
    # Parse the SVG file
    tree = parse_svg(svg_image_path)
    root = tree.getroot()
    target_groups, target_circles = find_circle_group(root)

    # Change the color in target group to a new color
    if len(target_groups) > group_nb:
        target_circles[group_nb].attrib["fill"] = new_color

    # Write the parsed file to the same svg file
    tree.write(svg_image_path)



# Get SVG Path
if __name__ == "__main__":
    change_circle_color_to("gui/images/svg_images/radio_btn_pressed.svg", 0, "#FFFF00")
