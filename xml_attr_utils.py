import xml.etree.ElementTree as ET

# Helper functions for types of attributes
def get_boolean_attribute(xml_node, attribute_id, default=False):
    """
    Get a boolean attribute from an XML node.

    Args:
        xml_node (xml.etree.ElementTree.Element): The XML node.
        attribute_id (str): The attribute ID to search for.
        default (bool): The default value if the attribute is not found.

    Returns:
        bool: The boolean value of the attribute.
    """
    attr_elem = xml_node.find(f"./attribute[@id='{attribute_id}']")
    if attr_elem is not None:
        value = attr_elem.attrib.get('value', '').strip().lower()
        return value == 'true'
    return default

def get_int_attribute(xml_node, attribute_id, default=0):
    """
    Get an integer attribute from an XML node.

    Args:
        xml_node (xml.etree.ElementTree.Element): The XML node.
        attribute_id (str): The attribute ID to search for.
        default (int): The default value if the attribute is not found.

    Returns:
        int: The integer value of the attribute.
    """
    attr_elem = xml_node.find(f"./attribute[@id='{attribute_id}']")
    return int(attr_elem.attrib.get('value', str(default))) if attr_elem is not None else default

def get_string_attribute(xml_node, attribute_id, default=''):
    """
    Get a string attribute from an XML node.

    Args:
        xml_node (xml.etree.ElementTree.Element): The XML node.
        attribute_id (str): The attribute ID to search for.
        default (str): The default value if the attribute is not found.

    Returns:
        str: The string value of the attribute.
    """
    attr_elem = xml_node.find(f"./attribute[@id='{attribute_id}']")
    return attr_elem.attrib.get('value', default) if attr_elem is not None else default

def get_attribute(xml_node, attr_id, default=None, cast=str):
    attr_elem = xml_node.find(f"./attribute[@id='{attr_id}']")
    return cast(attr_elem.attrib.get('value', default)) if attr_elem else default