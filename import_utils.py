import xml.etree.ElementTree as ET
import bpy
import uuid
import os
from .xml_attr_utils import (get_boolean_attribute, get_int_attribute, get_string_attribute)
from .options import skill_options

#Set up the node tree, load localization data, and parse global attributes, speakers etc."""
def initialize_node_tree(context, root, log_entries):
    # Load localisation data if available
    prefs = context.preferences.addons["Dialog Node Editor"].preferences
    localisation_path = prefs.localisation_path
    localisation_data = {}

    if localisation_path and os.path.exists(localisation_path):
        loc_tree = ET.parse(localisation_path)
        loc_root = loc_tree.getroot()
        for content in loc_root.findall(".//content"):
            contentuid = content.attrib.get('contentuid', '')
            text = content.text or ''
            localisation_data[contentuid] = text
        log_entries.append(f"Loaded localisation data for {len(localisation_data)} entries.")

    # Create a new DialogueNodeTree
    node_tree = bpy.data.node_groups.new("Dialogue Tree", "DialogueNodeTree")
    node_tree.category = "Generic NPC Dialog"  # Change this to a list of available categories later
    node_tree.UUID = str(uuid.uuid4())  # Generate a unique UUID if created manually
    node_tree.TimelineId = ""
    context.space_data.node_tree = node_tree

    # Extract and assign global attributes
    category_elem = root.find(".//attribute[@id='category']")
    uuid_elem = root.find(".//attribute[@id='UUID']")
    timelineid_elem = root.find(".//attribute[@id='TimelineId']")

    node_tree.category = category_elem.attrib.get('value', '') if category_elem is not None else ''
    node_tree.UUID = uuid_elem.attrib.get('value', '') if uuid_elem is not None else ''
    node_tree.TimelineId = timelineid_elem.attrib.get('value', '') if timelineid_elem is not None else ''

    # Parse Default Addressed Speakers
    for speaker in root.findall(".//node[@id='DefaultAddressedSpeakers']/children/node[@id='Object']"):
        item = node_tree.DefaultAddressedSpeakers.add()
        item.MapKey = int(speaker.find("./attribute[@id='MapKey']").attrib.get('value', '0'))
        item.MapValue = int(speaker.find("./attribute[@id='MapValue']").attrib.get('value', '-1'))

    # Parse speakerlist
    for speaker in root.findall(".//node[@id='speakerlist']/children/node[@id='speaker']"):
        item = node_tree.Speakers.add()
        item.index = speaker.find("./attribute[@id='index']").attrib.get('value', '')
        item.list = speaker.find("./attribute[@id='list']").attrib.get('value', '')
        item.SpeakerMappingId = speaker.find("./attribute[@id='SpeakerMappingId']").attrib.get('value', '')

    return node_tree, localisation_data

# Function: Populate handles_texts collection with all available handles, lineids and texts
def populate_handles_texts(xml_node, dialogue_node, localisation_data, log_entries):
    tagged_text_nodes = xml_node.findall(".//node[@id='TaggedText']")
    for tagged_text_node in tagged_text_nodes:
        has_tag_rule_value = False
        has_tag_rule_elem = tagged_text_node.find("./attribute[@id='HasTagRule']")
        if has_tag_rule_elem is not None:
            has_tag_rule_value = has_tag_rule_elem.attrib.get('value', 'False') == 'True'

        # Process TagText nodes
        tag_text_nodes = tagged_text_node.findall(".//node[@id='TagText']")
        for tag_text_node in tag_text_nodes:
            tag_text_attr = tag_text_node.find("./attribute[@id='TagText']")
            if tag_text_attr is not None:
                handle = tag_text_attr.attrib.get('handle', '')
                version = int(tag_text_attr.attrib.get('version', 1))
            else:
                handle = ''
                version = 1

            text = localisation_data.get(handle, '')

            lineid_attr = tag_text_node.find("./attribute[@id='LineId']")
            lineid = lineid_attr.attrib.get('value', '') if lineid_attr is not None else ''

            stub_elem = tag_text_node.find("./attribute[@id='stub']")
            stub_value = stub_elem is not None and stub_elem.attrib.get('value', 'False') == 'True'

            # Add data to handles_texts
            handle_text_item = dialogue_node.handles_texts.add()
            handle_text_item.lineid = lineid
            handle_text_item.handle = handle
            handle_text_item.text = text
            handle_text_item.has_tag_rule = has_tag_rule_value
            handle_text_item.stub = stub_value
            handle_text_item.version = version

            # Log the added handle-text pair
            log_entries.append(
                f"Added Handle-Text pair: handle={handle}, text={text}, version={version}, "
                f"has_tag_rule={has_tag_rule_value}, stub={stub_value}"
            )

# Function: Populate set and checked flags
def populate_flags(xml_node, dialogue_node, log_entries):
    # Populate SetFlags
    dialogue_node.SetFlags.clear()
    setflags_node = xml_node.find(".//node[@id='setflags']")
    if setflags_node is not None:
        for flaggroup_node in setflags_node.findall(".//node[@id='flaggroup']"):
            flag_type = get_string_attribute(flaggroup_node, 'type', default="Global")
            for flag_node in flaggroup_node.findall(".//node[@id='flag']"):
                flag_uuid = get_string_attribute(flag_node, 'UUID', default="")
                is_true = get_boolean_attribute(flag_node, 'value', default=False)
                paramval = get_int_attribute(flag_node, 'paramval', default=None)

                set_flag = dialogue_node.SetFlags.add()
                set_flag.name = flag_uuid
                set_flag.is_true = is_true
                set_flag.flag_type = flag_type
                if paramval is not None:
                    set_flag.has_paramval = True
                    set_flag.paramval = paramval
                log_entries.append(f"Added SetFlag: {flag_uuid}, Type: {flag_type}, is_true: {is_true}")

    # Populate CheckFlags
    dialogue_node.CheckFlags.clear()
    checkflags_node = xml_node.find(".//node[@id='checkflags']")
    if checkflags_node is not None:
        for flaggroup_node in checkflags_node.findall(".//node[@id='flaggroup']"):
            flag_type = get_string_attribute(flaggroup_node, 'type', default="Global")
            for flag_node in flaggroup_node.findall(".//node[@id='flag']"):
                flag_uuid = get_string_attribute(flag_node, 'UUID', default="")
                is_true = get_boolean_attribute(flag_node, 'value', default=False)
                paramval = get_int_attribute(flag_node, 'paramval', default=0)

                check_flag = dialogue_node.CheckFlags.add()
                check_flag.name = flag_uuid
                check_flag.is_true = is_true
                check_flag.flag_type = flag_type
                if paramval is not None:
                    check_flag.has_paramval = True
                    check_flag.paramval = paramval
                log_entries.append(f"Added CheckFlag: {flag_uuid}, Type: {flag_type}, is_true: {is_true}")

# Function: Parse editor data (notes in CinematicNodeContext)
def process_editor_data(xml_node, dialogue_node, log_entries):
    editor_data_node = xml_node.find(".//node[@id='editorData']")
    if editor_data_node:
        for data_node in editor_data_node.findall(".//node[@id='data']"):
            key = get_string_attribute(data_node, 'key', default="")
            if key == "CinematicNodeContext":
                dialogue_node.cinematic_node_context = get_string_attribute(data_node, 'val', default="")
                log_entries.append(f"Set Cinematic Node Context: {dialogue_node.cinematic_node_context}")

def populate_roll_node(xml_node, roll_node, uuid, log_entries):
    roll_node.uuid = get_string_attribute(xml_node, 'UUID')

    roll_node.ShowOnce = get_boolean_attribute(xml_node, 'ShowOnce', default=False)
    roll_node.transitionmode = get_int_attribute(xml_node, 'transitionmode', default=0)
    roll_node.speaker = get_int_attribute(xml_node, 'speaker', default=0)
    roll_node.RollTargetSpeaker = get_int_attribute(xml_node, 'RollTargetSpeaker', default=0)
    roll_node.RollType = get_string_attribute(xml_node, 'RollType', default="")
    roll_node.Ability = get_string_attribute(xml_node, 'Ability', default="Wisdom")
    # Extract Skill
    skill_elem = xml_node.find("./attribute[@id='Skill']")
    skill = skill_elem.attrib.get('value', 'None') if skill_elem is not None else 'None'

    # Validate the skill against the allowed options - change this to a list that updates based on Ability
    if skill not in [item[0] for item in skill_options]:
        log_entries.append(f"Invalid skill '{skill}' for Roll node {uuid}. Defaulting to 'None'.")
        skill = 'None'

    roll_node.Skill = skill
    roll_node.Advantage = get_int_attribute(xml_node, 'Advantage', default=0)
    roll_node.ExcludeCompanionsOptionalBonuses = get_boolean_attribute(
		xml_node, 'ExcludeCompanionsOptionalBonuses', default=False
	)
    roll_node.ExcludeSpeakerOptionalBonuses = get_boolean_attribute(
		xml_node, 'ExcludeSpeakerOptionalBonuses', default=False
	)

    # Validate DifficultyClassID based on available options
    difficulty_class_id = get_string_attribute(xml_node, 'DifficultyClassID', default="")
    valid_dcs = [item[0] for item in roll_node.DifficultyClassID_options]
    if difficulty_class_id in valid_dcs:
        roll_node.DifficultyClassID = difficulty_class_id
    else:
        roll_node.DifficultyClassID = valid_dcs[0] if valid_dcs else ""
        log_entries.append(
			f"Warning: Invalid DifficultyClassID '{difficulty_class_id}' for Roll node {uuid}. "
			f"Set to default '{roll_node.DifficultyClassID}'."
		)

