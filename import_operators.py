import os
import uuid
import xml.etree.ElementTree as ET

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .import_utils import (initialize_node_tree, process_editor_data,
                           populate_handles_texts, populate_flags, populate_roll_node)
from .nodes import DialogueNodeTree, NestedDialogNode
from .xml_attr_utils import (get_boolean_attribute, get_int_attribute, get_string_attribute)


class AddSpeakerLinkingEntryOperator(bpy.types.Operator):
    bl_idname = "node.add_speaker_linking_entry"
    bl_label = "Add Speaker Linking Entry"

    def execute(self, context):
        node = context.active_node
        if isinstance(node, NestedDialogNode):
            new_entry = node.SpeakerLinkingEntry.add()
            max_key = max([entry.key for entry in node.SpeakerLinkingEntry], default=-1)
            max_value = max([entry.value for entry in node.SpeakerLinkingEntry], default=-1)
            new_entry.key = max_key + 1
            new_entry.value = max_value + 1
        return {'FINISHED'}


class RemoveSpeakerLinkingEntryOperator(bpy.types.Operator):
    bl_idname = "node.remove_speaker_linking_entry"
    bl_label = "Remove Speaker Linking Entry"

    index: bpy.props.IntProperty()

    def execute(self, context):
        node = context.active_node
        if isinstance(node, NestedDialogNode):
            node.SpeakerLinkingEntry.remove(self.index)
        return {'FINISHED'}

class AddDefaultSpeakerOperator(bpy.types.Operator):
    bl_idname = "node.add_default_speaker"
    bl_label = "Add Default Speaker"

    def execute(self, context):
        node_tree = context.space_data.node_tree
        if node_tree and node_tree.bl_idname == "DialogueNodeTree":
            # Add a new speaker
            new_default_speaker = node_tree.DefaultAddressedSpeakers.add()
            new_default_speaker.index = str(len(node_tree.Speakers))
            new_default_speaker.MapKey = 0
            new_default_speaker.MapValue = -1
        self.report({'INFO'}, f"Added new speaker with index {new_default_speaker.index}")
        return {'FINISHED'}

class RemoveDefaultSpeakerOperator(bpy.types.Operator):
    bl_idname = "node.remove_default_speaker"
    bl_label = "Remove Default Speaker"

    index: bpy.props.IntProperty()

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "No active Dialogue Node Tree")
            return {'CANCELLED'}

        if 0 <= self.index < len(node_tree.DefaultAddressedSpeakers):
            node_tree.DefaultAddressedSpeakers.remove(self.index)
            self.report({'INFO'}, f"Removed Default Addressed speaker at index {self.index}")
        else:
            self.report({'ERROR'}, f"Invalid index {self.index}")
        return {'FINISHED'}

class EditLongText(bpy.types.Operator):
    bl_idname = "node.edit_long_text"
    bl_label = "Edit Text"
    bl_options = {'REGISTER', 'UNDO'}

    text: bpy.props.StringProperty(name="Text", default="")

    def execute(self, context):
        # Update the original text property
        node = context.node
        node.handles_texts[self.index].text = self.text
        return {'FINISHED'}

    def invoke(self, context, event):
        node = context.node
        self.text = node.handles_texts[self.index].text
        return context.window_manager.invoke_props_dialog(self, width=900) #Find out if this can be increased in height

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "text", text="")

    index: bpy.props.IntProperty()

# Operator to create a new dialogue tree with a default node (e.g. Greeting)
class NewDialogueTreeOperator(bpy.types.Operator):
    bl_idname = "node.new_dialogue_tree"
    bl_label = "New Dialogue Tree"

    def execute(self, context):
        # Create a new DialogueNodeTree and set it as the active node tree
        node_tree = bpy.data.node_groups.new("Dialogue Tree", "DialogueNodeTree")
        context.space_data.node_tree = node_tree

        # Add a root node at the origin
        root_node = node_tree.nodes.new("DialogueLineNode")
        root_node.location = (0, 0)
        root_node.root = True

        # Add a child node and link it to the root node
        child_node = node_tree.nodes.new("DialogueLineNode")
        child_node.location = (500, 0)

        node_tree.links.new(root_node.outputs[0], child_node.inputs[0])

        return {'FINISHED'}

class RemoveDirectLinksOperator(bpy.types.Operator):
    bl_idname = "node.remove_direct_links_bypassing_reroutes"
    bl_label = "Remove Direct Links Bypassing Reroutes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Access the active DialogueNodeTree in the Node Editor
        node_tree = None
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR' and space.node_tree and space.node_tree.bl_idname == "DialogueNodeTree":
                        node_tree = space.node_tree
                        break

        if not node_tree:
            self.report({'WARNING'}, "No active DialogueNodeTree found in the Node Editor. You must have a DialogueNodeTree open.")
            return {'CANCELLED'}

        connections_removed = remove_direct_links_bypassing_reroutes(node_tree)
        self.report({'INFO'}, f"Removed {connections_removed} redundant direct connections.")
        return {'FINISHED'}

class AddDialogueNodeOperator(bpy.types.Operator):
    bl_idname = "node.add_dialogue_node"
    bl_label = "Add Dialogue Node"

    def execute(self, context):
        # Get the active node tree and check its type
        node_tree = context.space_data.node_tree
        if not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "Active node tree is not a DialogueNodeTree. You must have a DialogueNodeTree open.")
            return {'CANCELLED'}

        # Create a new node and set its location
        new_node = node_tree.nodes.new("DialogueLineNode")
        new_node.location = (300, 0)
        new_node.uuid = str(uuid.uuid4())

        # Link the new node to the first selected node if available
        selected_nodes = [node for node in node_tree.nodes if node.select]
        if selected_nodes:
            parent_node = selected_nodes[0]
            node_tree.links.new(parent_node.outputs[0], new_node.inputs[0])
            new_node.location = (parent_node.location.x + 400, parent_node.location.y)

        self.report({'INFO'}, f"Added new node with UUID: {new_node.uuid}")
        return {'FINISHED'}

class AddRollNodeOperator(bpy.types.Operator):
    bl_idname = "node.add_roll_node"
    bl_label = "Add Roll Node"

    def execute(self, context):
        # Get the active node tree and check its type
        node_tree = context.space_data.node_tree
        if not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "Active node tree is not a DialogueNodeTree")
            return {'CANCELLED'}

        # Create a new node and set its location
        new_node = node_tree.nodes.new("DialogueRollNode")
        new_node.location = (300, 0)
        new_node.uuid = str(uuid.uuid4())

        # Link the new node to the first selected node if available
        selected_nodes = [node for node in node_tree.nodes if node.select]
        if selected_nodes:
            parent_node = selected_nodes[0]
            node_tree.links.new(parent_node.outputs[0], new_node.inputs[0])
            new_node.location = (parent_node.location.x + 400, parent_node.location.y)

        self.report({'INFO'}, f"Added new node with UUID: {new_node.uuid}")
        return {'FINISHED'}

class AddSpeakerOperator(bpy.types.Operator):
    bl_idname = "node.add_speaker"
    bl_label = "Add Speaker"
    bl_description = "Add a new speaker to the speakerlist"

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "No active Dialogue Node Tree")
            return {'CANCELLED'}

        # Add a new speaker with an incremented index
        new_speaker = node_tree.Speakers.add()
        new_speaker.index = str(len(node_tree.Speakers))
        new_speaker.list = ""
        new_speaker.SpeakerMappingId = ""

        self.report({'INFO'}, f"Added new speaker with index {new_speaker.index}")
        return {'FINISHED'}

class RemoveSpeakerOperator(bpy.types.Operator):
    bl_idname = "node.remove_speaker"
    bl_label = "Remove Speaker"
    bl_description = "Remove the selected speaker from the speakerlist"

    index: bpy.props.IntProperty() 

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if not isinstance(node_tree, DialogueNodeTree):
            self.report({'ERROR'}, "No active Dialogue Node Tree")
            return {'CANCELLED'}

        if 0 <= self.index < len(node_tree.Speakers):
            node_tree.Speakers.remove(self.index)
            self.report({'INFO'}, f"Removed speaker at index {self.index}")
        else:
            self.report({'ERROR'}, f"Invalid index {self.index}")
        return {'FINISHED'}

class AddHandleTextOperator(bpy.types.Operator):
    bl_idname = "node.add_handle_text"
    bl_label = "Add Handle and Text"
    bl_description = "Add a new Handle-Text pair to a supported node"

    node_name: bpy.props.StringProperty()
    supported_node_types = {"DialogueLineNode", "DialogueRollNode", "DialogueAliasNode"}

    def execute(self, context):
        node_tree = context.space_data.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}

        node = node_tree.nodes.get(self.node_name)
        if not node:
            self.report({'ERROR'}, "Node not found")
            return {'CANCELLED'}

        if node.bl_idname not in self.supported_node_types:
            self.report({'ERROR'}, f"Target node type '{node.bl_idname}' is not supported")
            return {'CANCELLED'}

        if hasattr(node, "handles_texts"):
            item = node.handles_texts.add()
            item.handle = ""
            item.text = ""
            self.report({'INFO'}, f"Added new Handle-Text pair to node: {node.name}")
        else:
            self.report({'ERROR'}, "Node constructor type does not support handles and texts.")
            return {'CANCELLED'}

        return {'FINISHED'}


class RemoveHandleTextOperator(bpy.types.Operator):
    bl_idname = "node.remove_handle_text"
    bl_label = "Remove Handle and Text"
    bl_description = "Remove the selected Handle-Text pair from a supported node"

    node_name: bpy.props.StringProperty()
    index: bpy.props.IntProperty()
    supported_node_types = {"DialogueLineNode", "DialogueRollNode", "DialogueAliasNode"}

    def execute(self, context):

        node_tree = context.space_data.edit_tree
        if not node_tree:
            self.report({'ERROR'}, "No active node tree")
            return {'CANCELLED'}

        node = node_tree.nodes.get(self.node_name)
        if not node or node.bl_idname not in self.supported_node_types:
            self.report({'ERROR'}, "Target node is not a supported type")
            return {'CANCELLED'}

        if hasattr(node, "handles_texts") and 0 <= self.index < len(node.handles_texts):
            node.handles_texts.remove(self.index)
            self.report({'INFO'}, f"Removed Handle-Text pair at index {self.index}.")
        else:
            self.report({'ERROR'}, f"Invalid index or node does not support handles and texts")
            return {'CANCELLED'}

        return {'FINISHED'}

class AddSetFlagOperator(bpy.types.Operator):
    bl_idname = "node.add_setflag"
    bl_label = "Add Set Flag"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.node_tree.nodes.get(self.node_name)
        if node and hasattr(node, "SetFlags"):
            new_flag = node.SetFlags.add()
            new_flag.name = f""
            new_flag.is_true = False
        return {'FINISHED'}

class RemoveSetFlagOperator(bpy.types.Operator):
    bl_idname = "node.remove_setflag"
    bl_label = "Remove Set Flag"

    node_name: bpy.props.StringProperty()
    index: bpy.props.IntProperty()  # Index of the flag to remove

    def execute(self, context):
        node = context.space_data.node_tree.nodes.get(self.node_name)
        if node and hasattr(node, "SetFlags"):
            node.SetFlags.remove(self.index)
        return {'FINISHED'}


class AddCheckFlagOperator(bpy.types.Operator):
    bl_idname = "node.add_checkflag"
    bl_label = "Add Check Flag"

    node_name: bpy.props.StringProperty()

    def execute(self, context):
        node = context.space_data.node_tree.nodes.get(self.node_name)
        if node and hasattr(node, "CheckFlags"):
            new_flag = node.CheckFlags.add()
            new_flag.name = f""
            new_flag.is_true = False
        return {'FINISHED'}

class RemoveCheckFlagOperator(bpy.types.Operator):
    bl_idname = "node.remove_checkflag"
    bl_label = "Remove Check Flag"

    node_name: bpy.props.StringProperty()
    index: bpy.props.IntProperty()  # Index of the flag to remove

    def execute(self, context):
        node = context.space_data.node_tree.nodes.get(self.node_name)
        if node and hasattr(node, "CheckFlags"):
            node.CheckFlags.remove(self.index)
        return {'FINISHED'}


class ImportDialogueXML(Operator, ImportHelper):
    bl_idname = "node.import_dialogue_xml"
    bl_label = "Import Dialogue XML"
    bl_description = "Import dialogue nodes from an XML file and generate a node tree"
    filename_ext = ".xml"
    
    def __init__(self):
        # Initiliase maps as instance variables
        self.node_map = {}
        self.parent_child_map = {}

    def execute(self, context):
        log_entries = []
        try:
            # Parse the XML file
            tree = ET.parse(self.filepath)
            root = tree.getroot()

            # Initiliase node tree
            node_tree, localisation_data = initialize_node_tree(context, root, log_entries)

            # Log the global attributes assignment
            self.report(
                {'INFO'},
                f"Imported Dialogue Tree with UUID: {node_tree.UUID}, Category: {node_tree.category}, Timeline ID: {node_tree.TimelineId}"
            )
            
            # Handle Jump nodes
            parse_jump_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)
            
            # Handle Roll nodes
            parse_roll_nodes(root, node_tree, localisation_data, self.node_map, self.parent_child_map, log_entries)

            # Handle Roll Result nodes
            parse_rollresult_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)

            # Handle Alias nodes
            parse_alias_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)

            # Handle Visual State nodes
            parse_visualstate_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)

            #Handle Nested Dialog nodes
            parse_nesteddialog_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)

            #Handle Trade nodes
            parse_trade_nodes(root, node_tree, self.node_map, self.parent_child_map, log_entries)

            # Handle Dialogue Line nodes
            parse_dialogue_line_nodes(root, node_tree, localisation_data, self.node_map, self.parent_child_map, log_entries)

            # Process ValidatedFlags (what do they do?)
            process_validated_flags(node_tree, self.filepath, log_entries)
            
            # Link and connect nodes
            link_nodes(node_tree, self.node_map, self.parent_child_map, log_entries)
            
            # Save logs to the blend file directory
            blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
            log_path = os.path.join(blend_dir, "dialogue_import_log.txt")
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write("\n".join(log_entries))

            self.report({'INFO'}, f"Dialogue imported successfully! Log saved to: {log_path}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to import dialogue XML: {str(e)}")
            return {'CANCELLED'}

# ###### IMPORT FUNCTIONS FOR THE IMPORT OPERATOR ######
#Helper function to get children of nodes for connections
def extract_children(node, log_entries):
    children_uuids = []

    # Directly handle <node id="child">
    for child in node.findall(".//node[@id='child']"):
        child_uuid_element = child.find("./attribute[@id='UUID']")
        if child_uuid_element is not None:
            child_uuid = child_uuid_element.attrib.get('value', '')
            if child_uuid:
                children_uuids.append(child_uuid)
                log_entries.append(f"Extracted child UUID: {child_uuid}")
            else:
                log_entries.append(f"Child node missing UUID: {ET.tostring(child, encoding='unicode')}")
        else:
            log_entries.append(f"Malformed child node: {ET.tostring(child, encoding='unicode')}")

    # Handle additional layers of <node id='children'>
    for nested_children in node.findall(".//node[@id='children']/children"):
        nested_uuids = extract_children(nested_children, log_entries)
        children_uuids.extend(nested_uuids)

    return children_uuids

#Function: parse jump nodes
def parse_jump_nodes(root, node_tree, node_map, parent_child_map, log_entries):

    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")

            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue

            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')

            if constructor == 'Jump':
                # Handle Jump nodes specifically
                jumptarget_elem = xml_node.find("./attribute[@id='jumptarget']")
                jumptarget_uuid = jumptarget_elem.attrib.get('value', '') if jumptarget_elem is not None else None

                if not jumptarget_uuid:
                    log_entries.append(f"Jump node {uuid} missing jumptarget.")
                    continue

                # Extract jumptargetpoint attribute
                jumptargetpoint_elem = xml_node.find("./attribute[@id='jumptargetpoint']")
                jumptargetpoint = int(
                    jumptargetpoint_elem.attrib.get('value', '1')) if jumptargetpoint_elem is not None else 1

                jump_node = node_tree.nodes.new("DialogueJumpNode")
                jump_node.uuid = uuid
                jump_node.jumptarget = jumptarget_uuid
                jump_node.jumptargetpoint = jumptargetpoint
                jump_node.location = (0, 0)

                # Track node in the node map
                node_map[uuid] = jump_node
                parent_child_map[uuid] = [jumptarget_uuid]
                log_entries.append(f"Created Jump node: {uuid} with jumptarget {jumptarget_uuid}")

        except Exception as e:
            log_entries.append(f"Error processing Jump node: {str(e)}")

# Function: parse Dialogue Nodes (Greeting, Question, Answer, Cinematic)
def parse_dialogue_line_nodes(root, node_tree, localisation_data, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")
            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue

            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            log_entries.append(f"Inspecting Dialogue Line node: UUID={uuid}, Constructor={constructor}")

            # Check if the node is a Dialogue Line node
            if constructor in ('TagGreeting', 'TagQuestion', 'TagAnswer', 'TagCinematic',):
                try:
                    # Create Dialogue Line Node
                    dialogue_node = node_tree.nodes.new("DialogueLineNode")
                    dialogue_node.width = 400
                    dialogue_node.location = (0, 0)
                    dialogue_node.constructor = constructor
                    dialogue_node.uuid = uuid
                    dialogue_node.ShowOnce = get_boolean_attribute(xml_node, 'ShowOnce', default=False)
                    dialogue_node.groupid = get_string_attribute(xml_node, 'GroupID', default="")
                    dialogue_node.groupindex = get_int_attribute(xml_node, 'GroupIndex', default=0)
                    dialogue_node.root = get_boolean_attribute(xml_node, 'Root', default=False)
                    dialogue_node.endnode = get_boolean_attribute(xml_node, 'endnode', default=False)
                    dialogue_node.speaker = get_int_attribute(xml_node, 'speaker', default=0)
                    dialogue_node.approvalratingid = get_string_attribute(xml_node, 'ApprovalRatingID', default="")

                    # Parse editorData for Cinematic Node Context
                    process_editor_data(xml_node, dialogue_node, log_entries)

                    # Populate handles, lineids and texts
                    populate_handles_texts(xml_node, dialogue_node, localisation_data, log_entries)

                    # Populate setflags and checkflags
                    populate_flags(xml_node, dialogue_node, log_entries)

                    # Track node relationships
                    node_map[uuid] = dialogue_node
                    parent_child_map[uuid] = extract_children(xml_node, log_entries)
                    log_entries.append(f"Processed Dialogue Line node: UUID={uuid}")

                except Exception as e:
                    log_entries.append(f"Error processing node: {str(e)}")
        except Exception as e:
            log_entries.append(f"Error processing Dialogue Line node: {str(e)}")


# Function: parse Roll nodes
def parse_roll_nodes(root, node_tree, localisation_data, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")

            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue

            uuid = uuid_elem.attrib.get('value', '').strip()
            constructor = constructor_elem.attrib.get('value', '').strip()

            # Handle Roll nodes
            if constructor in ('ActiveRoll', 'PassiveRoll'):
                log_entries.append(f"Processing Roll node: UUID={uuid}, Constructor={constructor}")

                # Create and populate the Roll node
                roll_node = node_tree.nodes.new("DialogueRollNode")
                approvalratingid = get_string_attribute(xml_node, 'ApprovalRatingID', default="")
                roll_node.approvalratingid = approvalratingid
                populate_roll_node(xml_node, roll_node, uuid, log_entries)
                # Parse editorData for Cinematic Node Context
                process_editor_data(xml_node, roll_node, log_entries)
                # Populate handles, lineids and texts + flags
                populate_handles_texts(xml_node, roll_node, localisation_data, log_entries)
                populate_flags(xml_node, roll_node, log_entries)

                # Track node relationships
                node_map[uuid] = roll_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed Roll node: UUID={uuid}, Constructor={constructor_elem}")

        except Exception as e:
            log_entries.append(f"Error processing Roll node: {str(e)}")

# Function: parse RollResult nodes
def parse_rollresult_nodes(root, node_tree, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")

            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue

            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            if constructor == 'RollResult':
                log_entries.append(f"Processing RollResult node: UUID={uuid}, Constructor={constructor}")
                # Create and populate the RollResult node
                rollresult_node = node_tree.nodes.new("DialogueRollResultNode")
                rollresult_node.Success = get_boolean_attribute(xml_node, 'Success', default=False)
                populate_flags(xml_node, rollresult_node, log_entries)
                # Track node relationships
                node_map[uuid] = rollresult_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed Rollresult node: UUID={uuid}, Constructor={constructor_elem}")

        except Exception as e:
            log_entries.append(f"Error processing RollResult node: {str(e)}")

# Function: parse Alias Nodes
def parse_alias_nodes(root, node_tree, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")
            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue
            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            # Check if the node is an Alias node
            if constructor == 'Alias':
                # Create Alias Node
                alias_node = node_tree.nodes.new("DialogueAliasNode")
                alias_node.width = 400
                alias_node.location = (0, 0)
                alias_node.constructor = constructor
                alias_node.uuid = uuid
                alias_node.root = get_boolean_attribute(xml_node, 'Root', default=False)
                alias_node.greeting = get_boolean_attribute(xml_node, 'Greeting', default=False)
                alias_node.endnode = get_boolean_attribute(xml_node, 'endnode', default=False)
                alias_node.speaker = get_int_attribute(xml_node, 'speaker', default=0)
                alias_node.sourcenode = get_string_attribute(xml_node, 'SourceNode', default="")
                # Parse editorData for Cinematic Node Context
                process_editor_data(xml_node, alias_node, log_entries)
                # Populate setflags and checkflags
                populate_flags(xml_node, alias_node, log_entries)
                # Track node relationships
                node_map[uuid] = alias_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed Alias node: UUID={uuid}, Constructor={constructor_elem}")

        except Exception as e:
            log_entries.append(f"Error processing Dialogue Line node: {str(e)}")

# Function: parse Visual State nodes
def parse_visualstate_nodes(root, node_tree, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")
            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue
            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            # Check if the node is a Visual State node
            if constructor == 'Visual State':
                # Create Visual State Node
                visualstate_node = node_tree.nodes.new("DialogueVisualStateNode")
                visualstate_node.width = 400
                visualstate_node.location = (0, 0)
                visualstate_node.constructor = constructor
                visualstate_node.uuid = uuid
                visualstate_node.groupid = get_string_attribute(xml_node, 'GroupID', default="")
                visualstate_node.groupindex = get_int_attribute(xml_node, 'GroupIndex', default=0)
                # Parse editorData for Cinematic Node Context
                process_editor_data(xml_node, visualstate_node, log_entries)
                # Populate setflags and checkflags
                populate_flags(xml_node, visualstate_node, log_entries)
                # Track node relationships
                node_map[uuid] = visualstate_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed VisualState node: UUID={uuid}, Constructor={constructor_elem}")
        except Exception as e:
            log_entries.append(f"Error processing Visual State node: {str(e)}")

# Function: parse Nested Dialog nodes
def parse_nesteddialog_nodes(root, node_tree, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")
            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue
            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            # Check if the node is a Nested Dialog node
            if constructor == 'Nested Dialog':
                # Create Nested Dialog Node
                nesteddialog_node = node_tree.nodes.new("NestedDialogNode")
                nesteddialog_node.width = 400
                nesteddialog_node.location = (0, 0)
                nesteddialog_node.constructor = constructor
                nesteddialog_node.uuid = uuid
                nesteddialog_node.NestedDialogNodeUUID = get_string_attribute(xml_node, 'NestedDialogNodeUUID',
                                                                              default="")
                nesteddialog_node.root = get_boolean_attribute(xml_node, 'root', default=False)
                nesteddialog_node.endnode = get_boolean_attribute(xml_node, 'endnode', default=False)

                # Parse Speaker Linking Entries
                speaker_linking_node = xml_node.find(".//node[@id='SpeakerLinking']")
                if speaker_linking_node:
                    for entry_node in speaker_linking_node.findall(".//node[@id='SpeakerLinkingEntry']"):
                        entry = nesteddialog_node.SpeakerLinkingEntry.add()
                        entry.key = get_int_attribute(entry_node, 'Key')
                        entry.value = get_int_attribute(entry_node, 'Value')
                # Populate setflags and checkflags
                populate_flags(xml_node, nesteddialog_node, log_entries)
                # Parse editorData for Cinematic Node Context
                process_editor_data(xml_node, nesteddialog_node, log_entries)

                # Track node relationships
                node_map[uuid] = nesteddialog_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed NestedDialog node: UUID={uuid}, Constructor={constructor_elem}")
        except Exception as e:
            log_entries.append(f"Error processing Nested Dialog node: {str(e)}")

# Function: parse Trade nodes
def parse_trade_nodes(root, node_tree, node_map, parent_child_map, log_entries):
    for xml_node in root.findall(".//node[@id='node']"):
        try:
            # Extract UUID and constructor attributes
            uuid_elem = xml_node.find("./attribute[@id='UUID']")
            constructor_elem = xml_node.find("./attribute[@id='constructor']")
            if uuid_elem is None or constructor_elem is None:
                log_entries.append(
                    f"Skipping node due to missing UUID or constructor. XML: {ET.tostring(xml_node, encoding='unicode')}")
                continue
            uuid = uuid_elem.attrib.get('value', '')
            constructor = constructor_elem.attrib.get('value', '')
            # Check if the node is a Trade node
            if constructor == 'Trade':
                # Create Trade Node
                trade_node = node_tree.nodes.new("TradeNode")
                trade_node.width = 400
                trade_node.location = (0, 0)
                trade_node.constructor = constructor
                trade_node.uuid = uuid
                trade_node.speaker = get_int_attribute(xml_node, 'speaker', default=0)
                trade_node.trademode = get_int_attribute(xml_node, 'TradeMode', default=1)
                # Populate setflags and checkflags
                populate_flags(xml_node, trade_node, log_entries)
                # Track node relationships
                node_map[uuid] = trade_node
                parent_child_map[uuid] = extract_children(xml_node, log_entries)
                log_entries.append(f"Processed Trade node: UUID={uuid}, Constructor={constructor_elem}")
        except Exception as e:
            log_entries.append(f"Error processing Trade node: {str(e)}")

#Function: process ValidatedFlags sections
def process_validated_flags(node_tree, filepath, log_entries):
    tree = ET.parse(filepath)
    root = tree.getroot()
    for xml_node in root.findall(".//node[@id='node']"):
        uuid_elem = xml_node.find("./attribute[@id='UUID']")
        if uuid_elem is None:
            log_entries.append("Skipping node without UUID.")
            continue

        uuid = uuid_elem.attrib.get('value', '').strip()

        # Look for ValidatedFlags subnode
        validated_flags_node = xml_node.find("./children/node[@id='ValidatedFlags']")
        if validated_flags_node is not None:
            validated_has_value_elem = validated_flags_node.find("./attribute[@id='ValidatedHasValue']")
            if validated_has_value_elem is not None:
                validated_has_value = validated_has_value_elem.attrib.get('value', 'False') == 'True'
                # Add the UUID to validated_flags collection, regardless of True/False
                validated_entry = node_tree.validated_flags.add()
                validated_entry.uuid = uuid
                validated_entry.has_value = validated_has_value
                log_entries.append(
                    f"Node {uuid} has ValidatedFlags with ValidatedHasValue={validated_has_value}."
                )
            else:
                # If ValidatedFlags exists but ValidatedHasValue is missing
                log_entries.append(
                    f"Node {uuid} has ValidatedFlags, but no ValidatedHasValue attribute was found."
                )
        else:
            # Log that no ValidatedFlags were found for this node
            log_entries.append(f"No ValidatedFlags found for node {uuid}.")

#Function: connect and link nodes
def link_nodes(node_tree, node_map, parent_child_map, log_entries):
    missing_uuids = []

    for parent_uuid, children_uuids in parent_child_map.items():
        if parent_uuid not in node_map:
            log_entries.append(f"Parent node missing in node_map: {parent_uuid}")
        for child_uuid in children_uuids:
            if child_uuid not in node_map:
                log_entries.append(f"Child node missing in node_map: {child_uuid}")

    if missing_uuids:
        log_entries.append(f"Total missing nodes: {len(set(missing_uuids))}")

    # Link nodes
    for parent_uuid, children_uuids in parent_child_map.items():
        parent_node = node_map.get(parent_uuid)
        if not parent_node:
            log_entries.append(f"Missing parent node for UUID: {parent_uuid}")
            continue

        for child_uuid in children_uuids:
            child_node = node_map.get(child_uuid)
            if not child_node:
                log_entries.append(f"Missing child node for UUID: {child_uuid}")
                continue

            try:
                # Create a connection from the parent's output to the child's input
                node_tree.links.new(parent_node.outputs[0], child_node.inputs[0])
                log_entries.append(f"Linked node: {parent_uuid} -> {child_uuid}")
            except Exception as e:
                log_entries.append(f"Error linking nodes {parent_uuid} -> {child_uuid}: {e}")

    # Backup linking using GroupID and GroupIndex
    log_entries.append("Starting backup linking using GroupID and GroupIndex.")
    group_map = {}

    # Group nodes by GroupID if it is valid (not empty)
    for node in node_tree.nodes:
        group_id = getattr(node, 'groupid', None)
        group_index = getattr(node, 'groupindex', None)
        if group_id and group_id.strip():  # Ensure GroupID is not None or empty
            group_map.setdefault(group_id, []).append((group_index, node))

    # Link nodes in each group based on GroupIndex
    for group_id, nodes in group_map.items():
        nodes.sort(key=lambda x: x[0])  # Sort by GroupIndex
        for i in range(len(nodes) - 1):
            current_node = nodes[i][1]
            next_node = nodes[i + 1][1]
            try:
                node_tree.links.new(current_node.outputs[0], next_node.inputs[0])
                log_entries.append(f"Backup linked group nodes: {current_node.name} -> {next_node.name}")
            except AttributeError as e:
                log_entries.append(
                    f"Error backup linking group nodes: {current_node.name} -> {next_node.name}: {str(e)}")

# ###### ARRANGE ADDON UTILITY FUNCTIONS #####
def remove_direct_links_bypassing_reroutes(node_tree):
    connections_removed = 0

    if not node_tree:
        print("No valid node tree provided.")
        return connections_removed

    # Loop through all reroute nodes in the node tree
    for node in list(node_tree.nodes):  # Use list to avoid modifying the collection
        if node.type == 'REROUTE':
            # Ensure the reroute node has both input and output connections
            if node.inputs[0].is_linked and node.outputs[0].is_linked:
                input_socket = node.inputs[0].links[0].from_socket
                output_socket = node.outputs[0].links[0].to_socket

                # Look for redundant direct links bypassing the reroute and remove them
                for link in node_tree.links:
                    if link.from_socket == input_socket and link.to_socket == output_socket:
                        node_tree.links.remove(link)
                        connections_removed += 1

    return connections_removed


# Register and unregister operators
def register():
    bpy.utils.register_class(NewDialogueTreeOperator)
    bpy.utils.register_class(AddDialogueNodeOperator)
    bpy.utils.register_class(RemoveDirectLinksOperator)
    bpy.utils.register_class(AddRollNodeOperator)
    bpy.utils.register_class(AddSpeakerOperator)
    bpy.utils.register_class(RemoveSpeakerOperator)
    bpy.utils.register_class(AddDefaultSpeakerOperator)
    bpy.utils.register_class(RemoveDefaultSpeakerOperator)
    bpy.utils.register_class(AddSpeakerLinkingEntryOperator)
    bpy.utils.register_class(RemoveSpeakerLinkingEntryOperator)
    bpy.utils.register_class(AddHandleTextOperator)
    bpy.utils.register_class(RemoveHandleTextOperator)
    bpy.utils.register_class(AddSetFlagOperator)
    bpy.utils.register_class(RemoveSetFlagOperator)
    bpy.utils.register_class(AddCheckFlagOperator)
    bpy.utils.register_class(RemoveCheckFlagOperator)
    bpy.utils.register_class(ImportDialogueXML)
    bpy.utils.register_class(EditLongText)


def unregister():
    bpy.utils.unregister_class(NewDialogueTreeOperator)
    bpy.utils.unregister_class(AddDialogueNodeOperator)
    bpy.utils.unregister_class(AddRollNodeOperator)
    bpy.utils.unregister_class(AddSpeakerOperator)
    bpy.utils.unregister_class(RemoveSpeakerOperator)
    bpy.utils.unregister_class(AddDefaultSpeakerOperator)
    bpy.utils.unregister_class(RemoveDefaultSpeakerOperator)
    bpy.utils.unregister_class(AddSpeakerLinkingEntryOperator)
    bpy.utils.unregister_class(RemoveSpeakerLinkingEntryOperator)
    bpy.utils.unregister_class(RemoveDirectLinksOperator)
    bpy.utils.unregister_class(AddHandleTextOperator)
    bpy.utils.unregister_class(RemoveHandleTextOperator)
    bpy.utils.unregister_class(AddSetFlagOperator)
    bpy.utils.unregister_class(RemoveSetFlagOperator)
    bpy.utils.unregister_class(AddCheckFlagOperator)
    bpy.utils.unregister_class(RemoveCheckFlagOperator)
    bpy.utils.unregister_class(ImportDialogueXML)
    bpy.utils.unregister_class(EditLongText)